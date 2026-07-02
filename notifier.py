import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

def send_email_report(report_html: str, recipient_email: str):
    """
    Sends the generated HTML report to the specified email address.
    """
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    
    if not sender_email or not sender_password:
        print("Email credentials not found in environment variables. Skipping email send.")
        print("--- REPORT PREVIEW ---")
        print(report_html)
        print("----------------------")
        return

    msg = MIMEMultipart("alternative")
    msg['Subject'] = "Weekly AI Website Health Report"
    msg['From'] = sender_email
    msg['To'] = recipient_email

    # Attach HTML content
    part = MIMEText(report_html, "html")
    msg.attach(part)

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        print(f"Report successfully sent to {recipient_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")
