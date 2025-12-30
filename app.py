from dotenv import load_dotenv
load_dotenv()

import os
import json
import re
import threading
import uuid
import time
import imaplib
import email
from email.header import decode_header
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_from_directory

from google import genai
from google.genai import types
from slack_notifier import post_to_slack  # ← ADD THIS LINE


# ----------------------------
# Config
# ----------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
DAILY_CHECK_TIME = os.getenv("DAILY_CHECK_TIME", "14:00")  # Default: 2:00 PM
CHECK_RECENT_DAYS = int(os.getenv("CHECK_RECENT_DAYS", "7"))  # Only check emails from last N days
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_PDF_MB = float(os.getenv("MAX_PDF_MB", "15"))

# Initialize Gemini client only if API key is provided (optional for manual interface usage)
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
app = Flask(__name__)

# ----------------------------
# In-memory job store
# ----------------------------
jobs: Dict[str, Dict[str, Any]] = {}
check_history: List[Dict[str, Any]] = []  # Track when checks happened


# ----------------------------
# Verification Constants
# ----------------------------
EXPECTED_VENDOR = "Nexus Path Consulting Group LLC"
EXPECTED_HOURLY_RATE = 350.00
EXPECTED_WORKSHOP_FEE = 8500.00
EXPECTED_SUBTOTAL = 29570.50
EXPECTED_TAX_RATE = 0.08875
EXPECTED_TOTAL = 32194.88
EXPECTED_NET_DAYS = 30


# ----------------------------
# Helpers
# ----------------------------
def extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON from Gemini response"""
    fenced = re.search(r"```(?:json)?\s*({.*?})\s*```", text, flags=re.S)
    if fenced:
        return json.loads(fenced.group(1))
    brace = re.search(r"({[\s\S]*})", text)
    if brace:
        return json.loads(brace.group(1))
    raise ValueError("No JSON found in Gemini output")


def normalize(d: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize extracted data"""
    def fnum(v):
        try:
            return float(re.sub(r"[^\d.\-]", "", str(v)))
        except Exception:
            return 0.0

    def fstr(v):
        return str(v).strip() if v else ""

    def flist(v):
        return v if isinstance(v, list) else []

    return {
        "invoice_number": fstr(d.get("invoice_number")),
        "vendor": fstr(d.get("vendor")),
        "invoice_date": fstr(d.get("invoice_date")),
        "due_date": fstr(d.get("due_date")),
        "currency": fstr(d.get("currency", "USD")),
        "subtotal": fnum(d.get("subtotal")),
        "tax": fnum(d.get("tax")),
        "total": fnum(d.get("total")),
        "confidence": min(1.0, max(0.0, fnum(d.get("confidence")))),
        "flags": flist(d.get("flags")),
        "summary": fstr(d.get("summary")),
    }


def verify_invoice(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strict verification of invoice against expected values.
    Returns verification results with flags.
    """
    verification = {
        "vendor_match": False,
        "hourly_rate_match": False,
        "workshop_fee_match": False,
        "subtotal_match": False,
        "total_match": False,
        "tax_calculation_match": False,
        "net_30_terms_match": False,
        "all_checks_passed": False,
        "flags": [],
        "details": {}
    }

    # Vendor Check
    vendor_clean = data["vendor"].strip()
    if vendor_clean == EXPECTED_VENDOR:
        verification["vendor_match"] = True
        verification["details"]["vendor"] = f"✓ Vendor matches: {EXPECTED_VENDOR}"
    else:
        verification["flags"].append(f"Vendor mismatch: Expected '{EXPECTED_VENDOR}', got '{vendor_clean}'")
        verification["details"]["vendor"] = f"✗ Vendor mismatch"

    # Subtotal Check
    subtotal_diff = abs(data["subtotal"] - EXPECTED_SUBTOTAL)
    if subtotal_diff < 0.01:
        verification["subtotal_match"] = True
        verification["details"]["subtotal"] = f"✓ Subtotal matches: ${EXPECTED_SUBTOTAL:,.2f}"
    else:
        verification["flags"].append(f"Subtotal mismatch: Expected ${EXPECTED_SUBTOTAL:,.2f}, got ${data['subtotal']:,.2f}")
        verification["details"]["subtotal"] = f"✗ Subtotal mismatch"

    # Tax Calculation Check
    expected_tax = EXPECTED_SUBTOTAL * EXPECTED_TAX_RATE
    tax_diff = abs(data["tax"] - expected_tax)
    if tax_diff < 0.01:
        verification["tax_calculation_match"] = True
        verification["details"]["tax"] = f"✓ Tax calculation correct: ${expected_tax:,.2f} (8.875%)"
    else:
        verification["flags"].append(f"Tax calculation error: Expected ${expected_tax:,.2f}, got ${data['tax']:,.2f}")
        verification["details"]["tax"] = f"✗ Tax calculation mismatch"

    # Total Check
    total_diff = abs(data["total"] - EXPECTED_TOTAL)
    if total_diff < 0.01:
        verification["total_match"] = True
        verification["details"]["total"] = f"✓ Total matches: ${EXPECTED_TOTAL:,.2f}"
    else:
        verification["flags"].append(f"Total mismatch: Expected ${EXPECTED_TOTAL:,.2f}, got ${data['total']:,.2f}")
        verification["details"]["total"] = f"✗ Total mismatch"

    # Net 30 Terms Check
    try:
        inv_date = datetime.strptime(data["invoice_date"], "%Y-%m-%d")
        due_date = datetime.strptime(data["due_date"], "%Y-%m-%d")
        days_diff = (due_date - inv_date).days
        
        if days_diff == EXPECTED_NET_DAYS:
            verification["net_30_terms_match"] = True
            verification["details"]["terms"] = f"✓ Net 30 terms confirmed: {data['invoice_date']} + 30 days = {data['due_date']}"
        else:
            verification["flags"].append(f"Terms mismatch: Expected Net 30, got {days_diff} days")
            verification["details"]["terms"] = f"✗ Terms mismatch: {days_diff} days"
    except Exception as e:
        verification["flags"].append(f"Date parsing error: {str(e)}")
        verification["details"]["terms"] = f"✗ Could not verify terms"

    # Price Tag Verification
    summary_lower = data.get("summary", "").lower()
    if "$350" in data.get("summary", "") or "350.00" in data.get("summary", ""):
        verification["hourly_rate_match"] = True
        verification["details"]["hourly_rate"] = f"✓ Hourly rate $350.00 detected"
    else:
        verification["flags"].append("Hourly rate $350.00 not explicitly confirmed in summary")
        verification["details"]["hourly_rate"] = f"⚠ Hourly rate not confirmed in summary"

    if "$8,500" in data.get("summary", "") or "8500" in data.get("summary", ""):
        verification["workshop_fee_match"] = True
        verification["details"]["workshop_fee"] = f"✓ Workshop fee $8,500.00 detected"
    else:
        verification["flags"].append("Workshop fee $8,500.00 not explicitly confirmed in summary")
        verification["details"]["workshop_fee"] = f"⚠ Workshop fee not confirmed in summary"

    # Overall Pass/Fail
    critical_checks = [
        verification["vendor_match"],
        verification["subtotal_match"],
        verification["total_match"],
        verification["tax_calculation_match"],
        verification["net_30_terms_match"]
    ]
    
    verification["all_checks_passed"] = all(critical_checks)

    return verification


def print_verification_report(job_id: str, data: Dict[str, Any], verification: Dict[str, Any]):
    """Print detailed verification report to console"""
    print("\n" + "="*80)
    print(f"INVOICE VERIFICATION REPORT - Job ID: {job_id}")
    print("="*80)
    print(f"\nInvoice Number: {data['invoice_number']}")
    print(f"Vendor: {data['vendor']}")
    print(f"Invoice Date: {data['invoice_date']}")
    print(f"Due Date: {data['due_date']}")
    print(f"Currency: {data['currency']}")
    print(f"\nFinancial Summary:")
    print(f"  Subtotal: ${data['subtotal']:,.2f}")
    print(f"  Tax: ${data['tax']:,.2f}")
    print(f"  Total: ${data['total']:,.2f}")
    
    print(f"\n{'VERIFICATION CHECKS':^80}")
    print("-"*80)
    for key, value in verification["details"].items():
        print(f"  {value}")
    
    print(f"\n{'OVERALL STATUS':^80}")
    print("-"*80)
    if verification["all_checks_passed"]:
        print("  ✓✓✓ ALL CRITICAL CHECKS PASSED ✓✓✓")
    else:
        print("  ✗✗✗ VERIFICATION FAILED ✗✗✗")
    
    if verification["flags"]:
        print(f"\n{'FLAGS & ISSUES':^80}")
        print("-"*80)
        for flag in verification["flags"]:
            print(f"  ⚠ {flag}")
    
    print("\n" + "="*80 + "\n")


def run_gemini(job_id: str, pdf_bytes: bytes, context: Dict[str, str], client_override=None, model_override=None):
    """Process PDF with Gemini and verify results"""
    # Use provided client/model or defaults
    pdf_client = client_override if client_override else client
    pdf_model = model_override if model_override else MODEL_NAME
    
    try:
        prompt = f"""
Extract invoice fields and return STRICT JSON with keys:
invoice_number, vendor, invoice_date (YYYY-MM-DD), due_date (YYYY-MM-DD),
currency, subtotal, tax, total, confidence, flags, summary.

In the summary field, include details about pricing (hourly rates, flat fees) if visible.

Email context (may help):
From: {context.get("email_from")}
Subject: {context.get("email_subject")}
"""

        response = pdf_client.models.generate_content(
            model=pdf_model,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                system_instruction="Return only JSON. No markdown. Use YYYY-MM-DD for dates."
            ),
        )

        data = extract_json(response.text)
        parsed = normalize(data)
        
        # Run verification
        verification = verify_invoice(parsed)
        
        # Print verification report
        print_verification_report(job_id, parsed, verification)
        
        # ============================================================
        # POST TO SLACK
        # ============================================================
        slack_result = None
        try:
            # Post all invoices to Slack (or only verified ones if you prefer)
            if True:  # Change to: if verification.get("all_checks_passed"):  to post only verified
                print(f"\n📤 Posting to Slack channel...")
                
                slack_result = post_to_slack(
                    invoice_data=parsed,
                    pdf_bytes=pdf_bytes,
                    job_id=job_id,
                    verification=verification,
                    email_context={
                        "email_from": context.get("email_from", ""),
                        "email_subject": context.get("email_subject", "")
                    }
                )
                
                if slack_result["success"]:
                    print(f"✅ Posted to Slack successfully")
                else:
                    print(f"⚠️  Slack posting failed: {slack_result['error']}")
                    
        except Exception as e:
            print(f"⚠️  Slack error (continuing anyway): {str(e)}")
        # ============================================================
        
        # Update job status
        jobs[job_id] = {
            "status": "done",
            "result": parsed,
            "verification": verification,
            "slack_posted": slack_result,
            "processed_at": datetime.utcnow().isoformat() + "Z",
            "source": context.get("source", "unknown"),
            "filename": context.get("filename", "N/A"),
            "email_from": context.get("email_from", ""),
            "email_subject": context.get("email_subject", "")
        }

    except Exception as e:
        jobs[job_id] = {
            "status": "error",
            "error": str(e),
            "processed_at": datetime.utcnow().isoformat() + "Z"
        }
        print(f"\n✗ Error processing {job_id}: {str(e)}\n")


def decode_email_subject(subject_header: str) -> str:
    """Decode email subject line"""
    if not subject_header:
        return ""
    decoded_parts = decode_header(subject_header)
    subject = ""
    for content, encoding in decoded_parts:
        if isinstance(content, bytes):
            subject += content.decode(encoding or "utf-8", errors="ignore")
        else:
            subject += str(content)
    return subject


def get_pdf_attachments(msg) -> List[tuple]:
    """Extract PDF attachments from email message"""
    attachments = []
    
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get("Content-Disposition") is None:
            continue
        
        filename = part.get_filename()
        if filename and filename.lower().endswith(".pdf"):
            pdf_data = part.get_payload(decode=True)
            if pdf_data:
                attachments.append((filename, pdf_data))
    
    return attachments


def check_gmail_inbox(trigger_source: str = "scheduled", user_email=None, user_pass=None, user_api_key=None, user_model=None) -> Dict[str, Any]:
    """
    Check Gmail inbox for invoice emails and process them.
    Returns summary of what was found and processed.
    
    Optional parameters allow students to provide their own credentials.
    """
    # Use provided credentials or fallback to server defaults
    gmail_user = user_email or GMAIL_USER
    gmail_pass = user_pass or GMAIL_APP_PASSWORD
    api_key = user_api_key or GEMINI_API_KEY
    model_name = user_model or MODEL_NAME
    
    # Create client with the appropriate API key
    pdf_client = genai.Client(api_key=api_key) if user_api_key else client
    
    result = {
        "checked_at": datetime.utcnow().isoformat() + "Z",
        "trigger": trigger_source,
        "invoices_found": 0,
        "invoices_processed": 0,
        "errors": [],
        "job_ids": []
    }
    
    try:
        print(f"\n{'='*80}")
        print(f"Gmail Check Initiated - Trigger: {trigger_source.upper()}")
        print(f"Time: {result['checked_at']}")
        print(f"Checking emails from last {CHECK_RECENT_DAYS} days")
        print(f"{'='*80}\n")
        
        # Connect to Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(gmail_user, gmail_pass)
        mail.select("INBOX")
        
        # Calculate date cutoff (N days ago)
        from datetime import date, timedelta
        cutoff_date = date.today() - timedelta(days=CHECK_RECENT_DAYS)
        date_str = cutoff_date.strftime("%d-%b-%Y")  # Format: 20-Dec-2024
        
        # Search for unread emails from the last N days
        # IMAP date format: SINCE date
        status, messages = mail.search(None, f'(UNSEEN SINCE {date_str})')
        
        if status == "OK":
            email_ids = messages[0].split()
            print(f"Found {len(email_ids)} unread emails in inbox")
            
            for email_id in email_ids:
                # Fetch email
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                
                if status != "OK":
                    continue
                
                # Parse email
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Get subject, from, and date
                subject = decode_email_subject(msg.get("Subject", ""))
                from_email = msg.get("From", "")
                date_str = msg.get("Date", "")
                
                # Parse date to make it more readable
                try:
                    from email.utils import parsedate_to_datetime
                    email_date = parsedate_to_datetime(date_str)
                    formatted_date = email_date.strftime("%Y-%m-%d %H:%M")
                except:
                    formatted_date = date_str[:20] if date_str else "Unknown"
                
                # Extract sender name/email for cleaner display
                sender_display = from_email
                if "<" in from_email and ">" in from_email:
                    # Extract just the email or name
                    sender_display = from_email.split("<")[0].strip() or from_email.split("<")[1].split(">")[0]
                
                # Check if "invoice" is in subject (case-insensitive)
                if "invoice" not in subject.lower():
                    print(f"  ⊗ [{formatted_date}] From: {sender_display[:30]} | {subject[:60]}")
                    continue
                
                result["invoices_found"] += 1
                
                print(f"\n📧 FOUND INVOICE EMAIL:")
                print(f"  Date: {formatted_date}")
                print(f"  From: {from_email}")
                print(f"  Subject: {subject}")
                
                # Get PDF attachments
                attachments = get_pdf_attachments(msg)
                
                if not attachments:
                    print(f"  ⚠ No PDF attachments found")
                    result["errors"].append(f"No PDF in email: {subject[:30]}")
                    continue
                
                # Process each PDF attachment
                for filename, pdf_bytes in attachments:
                    pdf_size_mb = len(pdf_bytes) / (1024 * 1024)
                    
                    if pdf_size_mb > MAX_PDF_MB:
                        print(f"  ✗ PDF too large: {filename} ({pdf_size_mb:.2f} MB)")
                        result["errors"].append(f"PDF too large: {filename}")
                        continue
                    
                    print(f"  ✓ Processing PDF: {filename} ({pdf_size_mb:.2f} MB)")
                    
                    # Create job
                    job_id = str(uuid.uuid4())
                    jobs[job_id] = {
                        "status": "processing",
                        "result": None,
                        "source": trigger_source,
                        "filename": filename,
                        "email_from": from_email,
                        "email_subject": subject,
                        "processed_at": datetime.utcnow().isoformat() + "Z"
                    }
                    
                    context = {
                        "email_from": from_email,
                        "email_subject": subject,
                    }
                    
                    # Process in same thread with student's client/model if provided
                    run_gemini(job_id, pdf_bytes, context, pdf_client, model_name)
                    
                    result["invoices_processed"] += 1
                    result["job_ids"].append(job_id)
        
        mail.close()
        mail.logout()
        
        print(f"\n{'='*80}")
        print(f"Gmail Check Complete")
        print(f"  Invoices found: {result['invoices_found']}")
        print(f"  Invoices processed: {result['invoices_processed']}")
        print(f"{'='*80}\n")
        
    except Exception as e:
        error_msg = f"Gmail check error: {str(e)}"
        print(f"\n✗ {error_msg}\n")
        result["errors"].append(error_msg)
    
    # Add to check history
    check_history.append(result)
    
    # Keep only last 100 checks in history
    if len(check_history) > 100:
        check_history.pop(0)
    
    return result


def scheduled_checker_loop():
    """
    Background thread that checks Gmail at the scheduled time each day.
    Only runs if server has configured credentials (GMAIL_USER, GMAIL_APP_PASSWORD, GEMINI_API_KEY).
    """
    # Check if server has configured credentials
    if not all([GMAIL_USER, GMAIL_APP_PASSWORD, GEMINI_API_KEY]):
        print(f"\n{'='*80}")
        print(f"Scheduled Gmail Monitor: DISABLED")
        print(f"  Reason: Missing server environment variables")
        print(f"  Students can still use the manual web interface")
        print(f"{'='*80}\n")
        return
    
    print(f"\n{'='*80}")
    print(f"Scheduled Gmail Monitor Started")
    print(f"  Email: {GMAIL_USER}")
    print(f"  Daily check time: {DAILY_CHECK_TIME} (24-hour format)")
    print(f"  Looking for: UNSEEN emails with 'invoice' in subject")
    print(f"{'='*80}\n")
    
    while True:
        try:
            # Parse scheduled time
            hour, minute = map(int, DAILY_CHECK_TIME.split(":"))
            
            # Get current time
            now = datetime.now()
            
            # Calculate next scheduled check time
            scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If scheduled time has passed today, schedule for tomorrow
            if now >= scheduled_time:
                scheduled_time += timedelta(days=1)
            
            # Calculate seconds until next check
            seconds_until_check = (scheduled_time - now).total_seconds()
            
            print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Next scheduled check: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')} ({seconds_until_check/3600:.1f} hours)")
            
            # Sleep until check time
            time.sleep(seconds_until_check)
            
            # Perform the check
            check_gmail_inbox(trigger_source="scheduled")
            
        except Exception as e:
            print(f"\n✗ Scheduler error: {str(e)}\n")
            # Sleep 1 hour before retrying on error
            time.sleep(3600)


# ----------------------------
# Routes
# ----------------------------
@app.get("/")
def index():
    """Serve the student interface"""
    return send_from_directory('templates', 'index.html')


@app.get("/health")
def health():
    """System health check"""
    now = datetime.now()
    hour, minute = map(int, DAILY_CHECK_TIME.split(":"))
    scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= scheduled_time:
        scheduled_time += timedelta(days=1)
    
    last_check = check_history[-1] if check_history else None
    
    # Check if scheduled monitoring is enabled
    monitoring_enabled = all([GMAIL_USER, GMAIL_APP_PASSWORD, GEMINI_API_KEY])
    
    return jsonify({
        "ok": True,
        "model": MODEL_NAME,
        "gmail_monitoring": {
            "enabled": monitoring_enabled,
            "email": GMAIL_USER if monitoring_enabled else "Not configured (use web interface)",
            "daily_check_time": DAILY_CHECK_TIME,
            "check_recent_days": CHECK_RECENT_DAYS,
            "next_scheduled_check": scheduled_time.isoformat() if monitoring_enabled else None,
            "last_check": last_check["checked_at"] if last_check else None,
            "last_check_found": last_check["invoices_found"] if last_check else 0,
        },
        "total_invoices_processed": len([j for j in jobs.values() if j.get("status") == "done"]),
        "total_checks_performed": len(check_history)
    })


@app.post("/check_gmail_now")
def manual_check():
    """
    Manually trigger Gmail check immediately.
    Accepts optional student credentials in request body:
    {
      "email": "student@gmail.com",
      "app_pass": "student app password",
      "api_key": "student Gemini API key",
      "model": "gemini-2.0-flash"
    }
    """
    data = request.get_json() or {}
    
    print("\n🔘 Manual Gmail check triggered by user")
    if data.get("email"):
        print(f"   Using student credentials: {data.get('email')}")
    
    result = check_gmail_inbox(
        trigger_source="manual",
        user_email=data.get("email"),
        user_pass=data.get("app_pass"),
        user_api_key=data.get("api_key"),
        user_model=data.get("model")
    )
    
    return jsonify({
        "status": "complete",
        "checked_at": result["checked_at"],
        "invoices_found": result["invoices_found"],
        "invoices_processed": result["invoices_processed"],
        "job_ids": result["job_ids"],
        "errors": result["errors"],
        "message": f"Checked Gmail: found {result['invoices_found']} invoice(s), processed {result['invoices_processed']}"
    })


@app.get("/check_history")
def get_check_history():
    """View history of Gmail checks (last 100)"""
    return jsonify({
        "total_checks": len(check_history),
        "history": check_history[-20:]  # Return last 20
    })


@app.post("/submit_invoice")
def submit_invoice():
    """Manual invoice submission endpoint (still available for testing)"""
    if "invoice_pdf" not in request.files:
        return jsonify({"error": "invoice_pdf missing"}), 400

    pdf = request.files["invoice_pdf"].read()
    if len(pdf) == 0:
        return jsonify({"error": "empty pdf"}), 400

    if len(pdf) / (1024 * 1024) > MAX_PDF_MB:
        return jsonify({"error": "pdf too large"}), 413

    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "status": "processing",
        "result": None,
        "source": "manual_upload",
        "processed_at": datetime.utcnow().isoformat() + "Z"
    }

    context = {
        "email_from": request.form.get("email_from", ""),
        "email_subject": request.form.get("email_subject", ""),
    }

    t = threading.Thread(
        target=run_gemini,
        args=(job_id, pdf, context),
        daemon=True,
    )
    t.start()

    return jsonify({
        "status": "accepted",
        "job_id": job_id
    })


def generate_status_summary(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate human-readable status summary"""
    summary = {
        "status": job_data.get("status", "unknown"),
        "message": "",
        "invoice_info": {},
        "verification_summary": {},
        "slack_summary": {},
        "warnings": []
    }
    
    # If error status
    if job_data.get("status") == "error":
        summary["message"] = f"❌ Processing failed: {job_data.get('error', 'Unknown error')}"
        return summary
    
    # If still processing
    if job_data.get("status") == "processing":
        summary["message"] = "⏳ Invoice is being processed..."
        return summary
    
    # Get invoice data
    result = job_data.get("result", {})
    verification = job_data.get("verification", {})
    slack_posted = job_data.get("slack_posted", {})
    
    # Invoice information
    if result:
        summary["invoice_info"] = {
            "invoice_number": result.get("invoice_number", "N/A"),
            "vendor": result.get("vendor", "N/A"),
            "total": f"{result.get('currency', 'USD')} {result.get('total', 0):,.2f}",
            "date": result.get("invoice_date", "N/A"),
            "due_date": result.get("due_date", "N/A")
        }
    
    # Verification summary
    if verification:
        passed_checks = sum([
            verification.get("vendor_match", False),
            verification.get("subtotal_match", False),
            verification.get("tax_calculation_match", False),
            verification.get("total_match", False),
            verification.get("net_30_terms_match", False)
        ])
        total_checks = 5
        
        all_passed = verification.get("all_checks_passed", False)
        
        summary["verification_summary"] = {
            "all_checks_passed": all_passed,
            "checks_passed": f"{passed_checks}/{total_checks}",
            "status": "✅ VERIFIED" if all_passed else "⚠️ FAILED",
            "details": verification.get("details", {})
        }
        
        # Add flags as warnings
        if verification.get("flags"):
            summary["warnings"].extend(verification["flags"])
    
    # Slack summary
    if slack_posted:
        if slack_posted.get("success"):
            summary["slack_summary"] = {
                "posted": True,
                "status": "✅ Posted to Slack",
                "channel": f"#{os.getenv('SLACK_CHANNEL_NAME', 'invoice-approval')}",
                "pdf_url": slack_posted.get("pdf_url"),
                "message_id": slack_posted.get("message_ts")
            }
        else:
            summary["slack_summary"] = {
                "posted": False,
                "status": "❌ Slack posting failed",
                "error": slack_posted.get("error")
            }
            summary["warnings"].append(f"Slack error: {slack_posted.get('error')}")
    else:
        summary["slack_summary"] = {
            "posted": False,
            "status": "⚠️ Not posted to Slack"
        }
    
    # Generate overall message
    invoice_num = result.get("invoice_number", "N/A")
    vendor = result.get("vendor", "N/A")
    total = result.get("total", 0)
    currency = result.get("currency", "USD")
    
    if verification.get("all_checks_passed"):
        summary["message"] = f"✅ Invoice {invoice_num} processed successfully - {currency} {total:,.2f} - Verified & Posted to Slack"
    else:
        summary["message"] = f"⚠️ Invoice {invoice_num} processed with warnings - {currency} {total:,.2f} - {passed_checks}/5 checks passed"
    
    return summary


@app.get("/job_status")
def job_status():
    """Check status of a processing job with enhanced summary"""
    job_id = request.args.get("job_id")
    if not job_id or job_id not in jobs:
        return jsonify({"error": "job_id not found"}), 404
    
    job_data = jobs[job_id]
    
    # Generate summary
    summary = generate_status_summary(job_data)
    
    # Return enhanced response
    return jsonify({
        "job_id": job_id,
        "summary": summary,
        "full_details": job_data
    })


@app.get("/job_summary")
def job_summary():
    """Get just the summary without full technical details"""
    job_id = request.args.get("job_id")
    if not job_id or job_id not in jobs:
        return jsonify({"error": "job_id not found"}), 404
    
    job_data = jobs[job_id]
    summary = generate_status_summary(job_data)
    
    return jsonify({
        "job_id": job_id,
        "summary": summary
    })


@app.get("/jobs")
def list_jobs():
    """List all processed jobs with summaries"""
    job_summaries = []
    
    for job_id, job_data in jobs.items():
        result = job_data.get("result", {})
        verification = job_data.get("verification", {})
        slack_posted = job_data.get("slack_posted", {})
        
        # Build summary for this job
        summary = {
            "job_id": job_id,
            "status": job_data["status"],
            "invoice_number": result.get("invoice_number", "N/A") if result else "N/A",
            "vendor": result.get("vendor", "N/A") if result else "N/A",
            "total": f"{result.get('currency', 'USD')} {result.get('total', 0):,.2f}" if result else "N/A",
            "verification_status": "✅ Verified" if verification.get("all_checks_passed") else "⚠️ Failed" if verification else "❓ Unknown",
            "slack_posted": "✅ Posted" if slack_posted and slack_posted.get("success") else "❌ Failed" if slack_posted else "➖ N/A",
            "processed_at": job_data.get("processed_at", "N/A"),
            "source": job_data.get("source", "unknown")
        }
        
        # Add message summary
        if job_data.get("status") == "done" and result:
            if verification.get("all_checks_passed"):
                summary["message"] = f"✅ {result.get('invoice_number', 'N/A')} - Verified & Posted"
            else:
                summary["message"] = f"⚠️ {result.get('invoice_number', 'N/A')} - Verification issues"
        elif job_data.get("status") == "error":
            summary["message"] = f"❌ Processing error"
        else:
            summary["message"] = f"⏳ Processing..."
        
        job_summaries.append(summary)
    
    return jsonify({
        "total": len(jobs),
        "jobs": job_summaries
    })


if __name__ == "__main__":
    # Start scheduled Gmail monitoring thread
    scheduler_thread = threading.Thread(
        target=scheduled_checker_loop,
        daemon=True
    )
    scheduler_thread.start()
    
    # Start Flask server
    print(f"\n🚀 Starting Flask server on port {os.getenv('PORT', '10000')}\n")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))