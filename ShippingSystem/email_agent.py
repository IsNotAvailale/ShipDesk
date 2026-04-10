"""
Email Agent — Gmail API + usaddress parsing.
Fetches unread emails, extracts client info, adds to DB.
"""
import os
import re
import json
import base64
import logging
from datetime import datetime

import usaddress
from apscheduler.schedulers.background import BackgroundScheduler

import database
from config import CREDENTIALS_DIR, EMAIL_AGENT_INTERVAL

logger = logging.getLogger(__name__)

# Gmail API scopes — read-only so we never modify or delete emails
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          "https://www.googleapis.com/auth/gmail.modify"]  # needed to mark read

TOKEN_FILE = os.path.join(CREDENTIALS_DIR, "gmail_token.json")
CREDS_FILE = os.path.join(CREDENTIALS_DIR, "gmail_credentials.json")

_scheduler = BackgroundScheduler()
_last_run_result = {"timestamp": None, "added": 0, "flagged": 0, "error": None}


def get_gmail_service():
    """Authenticate with Gmail API and return a service object."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CREDS_FILE):
                    raise FileNotFoundError(
                        f"Gmail credentials file not found at {CREDS_FILE}. "
                        "Download it from Google Cloud Console and place it there."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())

        from googleapiclient.discovery import build
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        logger.error(f"Gmail auth error: {e}")
        raise


def _get_email_body(msg) -> str:
    """Extract plain text body from a Gmail message."""
    payload = msg.get("payload", {})
    parts = payload.get("parts", [])
    body = ""
    if parts:
        for part in parts:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    break
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return body


def _extract_header(msg, name: str) -> str:
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _parse_email_field(text: str, patterns: list) -> str:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return ""


def parse_shipping_info(email_body: str, sender: str) -> dict:
    """
    Parse shipping info from freeform email text.
    Returns dict with keys: name, company, address, city, state, zip, email, phone
    and 'complete' (bool) indicating if all required fields were found.
    """
    text = email_body + "\n" + sender

    info = {
        "name": "",
        "company": "",
        "address": "",
        "city": "",
        "state": "",
        "zip": "",
        "email": "",
        "phone": "",
    }

    # Extract email address from sender or body
    email_match = re.search(r"[\w.+-]+@[\w-]+\.\w+", text)
    if email_match:
        info["email"] = email_match.group(0)

    # Extract phone number
    phone_match = re.search(
        r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}", text
    )
    if phone_match:
        info["phone"] = re.sub(r"[^\d]", "", phone_match.group(0))
        info["phone"] = f"({info['phone'][:3]}) {info['phone'][3:6]}-{info['phone'][6:]}"

    # Extract name — look for labeled patterns first
    info["name"] = _parse_email_field(text, [
        r"(?:ship\s+to|recipient|name|attention|attn)[:\s]+([A-Za-z][^\n,]{2,40})",
        r"^([A-Z][a-z]+ [A-Z][a-z]+)$",
    ])

    # Extract company
    info["company"] = _parse_email_field(text, [
        r"(?:company|business|firm|organization|org)[:\s]+([^\n,]{2,60})",
    ])

    # Try to isolate address lines then parse with usaddress
    # Look for lines that start with a number (likely a street address)
    lines = email_body.splitlines()
    candidate_blocks = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"^\d+\s+\w", stripped):
            # Grab this line plus the next 2 (city/state/zip likely follow)
            block = " ".join(l.strip() for l in lines[i:i+3] if l.strip())
            candidate_blocks.append(block)

    for block in candidate_blocks:
        try:
            tagged_dict, _ = usaddress.tag(block)
            number = tagged_dict.get("AddressNumber", "")
            pre_dir = tagged_dict.get("StreetNamePreDirectional", "")
            street = tagged_dict.get("StreetName", "")
            post_type = tagged_dict.get("StreetNamePostType", "")
            post_dir = tagged_dict.get("StreetNamePostDirectional", "")
            occ_type = tagged_dict.get("OccupancyType", "")
            occ_id = tagged_dict.get("OccupancyIdentifier", "")

            street_parts = [p for p in [number, pre_dir, street, post_type,
                                         post_dir, occ_type, occ_id] if p]
            if street_parts and number:
                info["address"] = " ".join(street_parts)
                info["city"] = info["city"] or tagged_dict.get("PlaceName", "")
                info["state"] = info["state"] or tagged_dict.get("StateName", "")
                info["zip"] = info["zip"] or tagged_dict.get("ZipCode", "")
                break
        except Exception as e:
            logger.debug(f"usaddress block parse error: {e}")
            continue

    # Fallback: labeled field extraction for structured emails
    if not info["address"]:
        info["address"] = _parse_email_field(email_body, [
            r"(?:address|street|addr)[:\s]+(\d+[^\n,]{3,60})",
        ])
    if not info["city"]:
        info["city"] = _parse_email_field(email_body, [
            r"(?:city)[:\s]+([^\n,]{2,40})",
        ])

    # Fallback regex for city/state/zip if usaddress missed them
    if not info["zip"]:
        zip_m = re.search(r"\b(\d{5})(?:-\d{4})?\b", text)
        if zip_m:
            info["zip"] = zip_m.group(1)

    if not info["state"]:
        state_m = re.search(
            r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|"
            r"ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|"
            r"PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b", text
        )
        if state_m:
            info["state"] = state_m.group(1)

    # Determine completeness — need at minimum name + address + city + state + zip
    required = ["name", "address", "city", "state", "zip"]
    info["complete"] = all(info[f] for f in required)

    return info


def run_email_agent(triggered_by: str = "scheduler") -> dict:
    """Main agent loop: fetch unread emails, parse, add to DB."""
    global _last_run_result
    added = 0
    flagged = 0
    error = None

    try:
        service = get_gmail_service()
        results = service.users().messages().list(
            userId="me", labelIds=["INBOX"], q="is:unread"
        ).execute()
        messages = results.get("messages", [])

        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full"
            ).execute()
            body = _get_email_body(msg)
            sender = _extract_header(msg, "From")
            subject = _extract_header(msg, "Subject")

            info = parse_shipping_info(body, sender)

            if info["complete"]:
                client_id = database.add_client(
                    name=info["name"],
                    company=info["company"],
                    address=info["address"],
                    city=info["city"],
                    state=info["state"],
                    zip_code=info["zip"],
                    email=info["email"],
                    phone=info["phone"],
                )
                database.add_log(
                    triggered_by, "Email Agent — Client Added",
                    f"From: {sender} | Subject: {subject} | ClientID: {client_id}"
                )
                added += 1
            else:
                database.add_log(
                    triggered_by, "Email Agent — Flagged Incomplete",
                    f"From: {sender} | Subject: {subject} | "
                    f"Parsed: {json.dumps({k: v for k, v in info.items() if k != 'complete'})}"
                )
                flagged += 1

            # Mark email as read (do not delete or modify content)
            service.users().messages().modify(
                userId="me",
                id=msg_ref["id"],
                body={"removeLabelIds": ["UNREAD"]}
            ).execute()

    except FileNotFoundError as e:
        error = str(e)
        logger.warning(error)
    except Exception as e:
        error = str(e)
        logger.error(f"Email agent error: {e}", exc_info=True)

    _last_run_result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "added": added,
        "flagged": flagged,
        "error": error,
    }
    return _last_run_result


def get_last_run_result() -> dict:
    return _last_run_result


def start_scheduler():
    if not _scheduler.running:
        _scheduler.add_job(
            run_email_agent,
            "interval",
            minutes=EMAIL_AGENT_INTERVAL,
            id="email_agent",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info(f"Email agent scheduler started (every {EMAIL_AGENT_INTERVAL} min)")
