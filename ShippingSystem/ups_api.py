"""
UPS Production REST API integration.
OAuth 2.0 Client Credentials flow → label generation → PDF save.
"""
import os
import base64
import logging
from datetime import datetime

import requests

import database
from config import (LABELS_DIR, UPS_SERVICE_CODE, UPS_PACKAGE_CODE,
                    UPS_WEIGHT_LBS, UPS_LENGTH, UPS_WIDTH, UPS_HEIGHT)
from crypto import load_ups_credentials

logger = logging.getLogger(__name__)

UPS_TOKEN_URL = "https://onlinetools.ups.com/security/v1/oauth/token"
UPS_SHIP_URL = "https://onlinetools.ups.com/api/shipments/v2403/ship"

_token_cache = {"token": None, "expires_at": 0}


def _get_token(creds: dict) -> str:
    """Fetch or return cached OAuth2 token."""
    import time
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    resp = requests.post(
        UPS_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(creds["client_id"], creds["client_secret"]),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + int(data.get("expires_in", 3600))
    return _token_cache["token"]


def _build_ship_request(creds: dict, shipment_row) -> dict:
    """Build the UPS Shipments API request payload."""
    return {
        "ShipmentRequest": {
            "Request": {
                "SubVersion": "1801",
                "RequestOption": "nonvalidate",
                "TransactionReference": {"CustomerContext": f"shipment-{shipment_row['id']}"}
            },
            "Shipment": {
                "Description": "Documents",
                "Shipper": {
                    "Name": creds.get("shipper_name", ""),
                    "AttentionName": creds.get("shipper_name", ""),
                    "ShipperNumber": creds.get("account_number", ""),
                    "Address": {
                        "AddressLine": [creds.get("shipper_address", "")],
                        "City": creds.get("shipper_city", ""),
                        "StateProvinceCode": creds.get("shipper_state", ""),
                        "PostalCode": creds.get("shipper_zip", ""),
                        "CountryCode": "US"
                    }
                },
                "ShipTo": {
                    "Name": shipment_row["name"],
                    "AttentionName": shipment_row["name"],
                    "Address": {
                        "AddressLine": [shipment_row["address"]],
                        "City": shipment_row["city"],
                        "StateProvinceCode": shipment_row["state"],
                        "PostalCode": shipment_row["zip"],
                        "CountryCode": "US"
                    }
                },
                "ShipFrom": {
                    "Name": creds.get("shipper_name", ""),
                    "Address": {
                        "AddressLine": [creds.get("shipper_address", "")],
                        "City": creds.get("shipper_city", ""),
                        "StateProvinceCode": creds.get("shipper_state", ""),
                        "PostalCode": creds.get("shipper_zip", ""),
                        "CountryCode": "US"
                    }
                },
                "PaymentInformation": {
                    "ShipmentCharge": {
                        "Type": "01",
                        "BillShipper": {"AccountNumber": creds.get("account_number", "")}
                    }
                },
                "Service": {"Code": UPS_SERVICE_CODE, "Description": "Next Day Air"},
                "Package": {
                    "Description": "Package",
                    "Packaging": {"Code": UPS_PACKAGE_CODE},
                    "Dimensions": {
                        "UnitOfMeasurement": {"Code": "IN"},
                        "Length": UPS_LENGTH,
                        "Width": UPS_WIDTH,
                        "Height": UPS_HEIGHT,
                    },
                    "PackageWeight": {
                        "UnitOfMeasurement": {"Code": "LBS"},
                        "Weight": UPS_WEIGHT_LBS
                    }
                }
            },
            "LabelSpecification": {
                "LabelImageFormat": {"Code": "PDF"},
                "HTTPUserAgent": "ShippingSystem/1.0"
            }
        }
    }


def ship_one(shipment_row) -> dict:
    """
    Process a single shipment. Returns:
    {"ok": True, "tracking": "...", "pdf_path": "..."}
    or {"ok": False, "error": "..."}
    """
    creds = load_ups_credentials()
    if not creds.get("client_id") or not creds.get("client_secret"):
        return {"ok": False, "error": "UPS credentials not configured."}

    try:
        token = _get_token(creds)
        payload = _build_ship_request(creds, shipment_row)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "transId": f"ship-{shipment_row['id']}",
            "transactionSrc": "ShippingSystem",
        }
        resp = requests.post(UPS_SHIP_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        result = data["ShipmentResponse"]["ShipmentResults"]
        tracking = result["ShipmentIdentificationNumber"]

        # Extract PDF label
        pkg_results = result.get("PackageResults", {})
        label_data = pkg_results.get("ShippingLabel", {}).get("GraphicImage", "")
        if not label_data:
            return {"ok": False, "error": "No label image in UPS response."}

        # Save PDF
        os.makedirs(LABELS_DIR, exist_ok=True)
        safe_name = re.sub(r"[^\w\-]", "_", shipment_row["name"])
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}_{safe_name}_{tracking}.pdf"
        pdf_path = os.path.join(LABELS_DIR, filename)
        with open(pdf_path, "wb") as f:
            f.write(base64.b64decode(label_data))

        return {"ok": True, "tracking": tracking, "pdf_path": pdf_path}

    except requests.HTTPError as e:
        err = f"UPS API HTTP {e.response.status_code}: {e.response.text[:300]}"
        logger.error(err)
        return {"ok": False, "error": err}
    except Exception as e:
        logger.error(f"UPS error: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


def process_all_pending(triggered_by: str) -> list:
    """Process all pending shipments. Returns list of result dicts."""
    pending = database.get_pending_shipments()
    results = []
    for shipment in pending:
        result = ship_one(shipment)
        result["shipment_id"] = shipment["id"]
        result["client_name"] = shipment["name"]
        if result["ok"]:
            database.complete_shipment(
                shipment["id"], result["tracking"], result["pdf_path"]
            )
            database.add_log(
                triggered_by, "Shipment Processed",
                f"Client: {shipment['name']} | Tracking: {result['tracking']}"
            )
        else:
            database.add_log(
                triggered_by, "Shipment Failed",
                f"Client: {shipment['name']} | Error: {result['error']}"
            )
        results.append(result)
    return results


# fix missing import
import re
