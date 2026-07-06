import os
from playwright.sync_api import sync_playwright

def html_to_pdf(html_path: str, pdf_path: str):
    """
    Converts a local HTML file to a PDF using Playwright.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file://{os.path.abspath(html_path)}", wait_until="networkidle")
        page.pdf(path=pdf_path, format="A4", print_background=True)
        browser.close()
