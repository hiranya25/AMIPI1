import os
from dotenv import load_dotenv
import database
from crawler import WebsiteCrawler
from ai_reporter import generate_report
from notifier import send_email_report

# Load environment variables (API keys, target URL, email settings)
load_dotenv()

TARGET_URL = os.getenv("TARGET_URL", "https://example.com")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "admin@example.com")
MAX_DEPTH = int(os.getenv("MAX_DEPTH", 2))

def run_weekly_audit():
    print(f"Starting Weekly Audit for {TARGET_URL}...")
    
    # 1. Init Database
    database.init_db()
    
    # 2. Get Previous Audit (for comparison)
    previous_report = database.get_last_audit(TARGET_URL)
    
    # 3. Crawl Website
    crawler = WebsiteCrawler(TARGET_URL)
    crawler.crawl(max_depth=MAX_DEPTH)
    current_report = crawler.get_report()
    
    # 4. Save New Audit
    database.save_audit(TARGET_URL, current_report)
    
    # 5. Generate AI Report
    print("Generating AI Report...")
    report_html = generate_report(current_report, previous_report)
    
    # 6. Send Email
    print("Sending Email Notification...")
    send_email_report(report_html, RECIPIENT_EMAIL)
    
    print("Audit Complete!")

if __name__ == "__main__":
    run_weekly_audit()
