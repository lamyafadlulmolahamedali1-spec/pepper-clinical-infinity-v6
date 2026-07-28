"""
Pepper Clinical Infinity V6 — Email Queue Sender
© 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved

Sends queued session reports to lamyafadlulmolahamedali1@gmail.com
Run manually or schedule with cron.

Setup Gmail App Password:
  1. Go to myaccount.google.com
  2. Security → 2-Step Verification → ON
  3. Security → App Passwords → Create
  4. Use generated password as SMTP_PASS
"""
import os, json, smtplib, logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("PepperEmail")

SMTP_HOST  = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT  = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER  = os.environ.get("SMTP_USER",  "lamyafadlulmolahamedali1@gmail.com")
SMTP_PASS  = os.environ.get("SMTP_PASS",  "")
QUEUE_FILE = "pending_email_reports.json"
SENT_FILE  = "sent_email_reports.json"

def send_queue():
    if not SMTP_PASS:
        log.warning("SMTP_PASS not set. Set environment variable SMTP_PASS=your_app_password")
        log.info("How to get Gmail App Password:")
        log.info("  1. Go to myaccount.google.com → Security → 2-Step Verification → ON")
        log.info("  2. Security → App Passwords → Generate → Copy the 16-char password")
        log.info("  3. Set: export SMTP_PASS=xxxx_xxxx_xxxx_xxxx")
        return

    try:
        queue = json.load(open(QUEUE_FILE)) if os.path.exists(QUEUE_FILE) else []
    except Exception as e:
        log.error(f"Cannot read queue: {e}"); return

    if not queue:
        log.info("No emails in queue."); return

    sent = json.load(open(SENT_FILE)) if os.path.exists(SENT_FILE) else []
    failed = []

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.ehlo(); server.starttls(); server.login(SMTP_USER, SMTP_PASS)
        log.info(f"Connected to {SMTP_HOST}")

        for item in queue:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = item.get("subject", "Pepper V6 Session Report")
                msg["From"]    = SMTP_USER
                msg["To"]      = item.get("to", SMTP_USER)

                body_text = item.get("body","")
                html_body = f"""
<html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px">
<div style="background:#040b1a;color:#e0e8ff;border-radius:12px;padding:24px;max-width:600px;margin:0 auto">
  <h1 style="color:#a78bfa;margin-top:0">🤖 Pepper Clinical Infinity V6</h1>
  <h2 style="color:#34d399">Session Report</h2>
  <pre style="background:#07090f;color:#e0e8ff;padding:16px;border-radius:8px;
              font-size:13px;line-height:1.8;white-space:pre-wrap">{body_text}</pre>
  <hr style="border-color:#1a2550;margin:20px 0">
  <p style="color:#6b7280;font-size:11px;text-align:center">
    Pepper Clinical Infinity V6 © 2026 Lamya Fadlulmola Hamed Ali<br>
    All Rights Reserved · HIPAA &amp; GDPR Compliant
  </p>
</div></body></html>
"""
                msg.attach(MIMEText(body_text, "plain"))
                msg.attach(MIMEText(html_body, "html"))
                server.sendmail(SMTP_USER, item["to"], msg.as_string())
                item["sent_at"] = datetime.now().isoformat()
                sent.append(item)
                log.info(f"✅ Sent: {item.get('subject','')[:60]}")
            except Exception as e:
                log.warning(f"Failed: {e}"); failed.append(item)

        server.quit()
    except Exception as e:
        log.error(f"SMTP error: {e}"); failed = queue

    # Save sent + failed
    json.dump(sent, open(SENT_FILE,"w"), indent=2, default=str)
    json.dump(failed, open(QUEUE_FILE,"w"), indent=2, default=str)
    log.info(f"Done: {len(sent)-len([x for x in sent if 'sent_at' not in x])} sent, {len(failed)} failed")

if __name__ == "__main__":
    send_queue()
