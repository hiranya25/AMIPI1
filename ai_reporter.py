import google.generativeai as genai
import os
from dotenv import load_dotenv
import json

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def generate_report(current_report: dict, previous_report: dict | None) -> str:
    """
    Compares the current report with the previous one and generates a summary 
    using Google Gemini API (or a fallback if no key is present).
    """
    
    # Simple logic to find fixed and new issues if previous report exists
    fixed_issues = []
    new_issues = []
    
    if previous_report:
        # Example logic for broken links
        prev_links = {link.get("url") for link in previous_report.get("broken_links", []) if link.get("url")}
        curr_links = {link.get("url") for link in current_report.get("broken_links", []) if link.get("url")}
        
        fixed_links = prev_links - curr_links
        new_links = curr_links - prev_links
        
        if fixed_links:
            fixed_issues.append(f"Fixed Broken Links: {', '.join(fixed_links)}")
        if new_links:
            new_issues.append(f"New Broken Links: {', '.join(new_links)}")
            
        # Add similar logic for other categories (alt tags, metadata)
        # For brevity, this is a simplified comparison
    
    prompt = f"""
    You are an expert AI Website Health Monitor. 
    Analyze the following website audit data and generate a professional weekly email report.
    
    The report MUST contain exactly these sections:
    1. Issues Fixed
    2. New Issues Identified
    3. 🔴 Critical Issues Requiring Attention
    
    Current Audit Data:
    {json.dumps(current_report, indent=2)}
    
    Comparison Findings (Fixed/New):
    Fixed: {fixed_issues if fixed_issues else 'None explicitly identified from diff'}
    New: {new_issues if new_issues else 'None explicitly identified from diff'}
    
    Please format the output in clean, readable HTML or Markdown suitable for an email.
    Keep it concise but informative. Critical issues include any broken links or missing titles.
    """
    
    if not api_key:
        # Fallback if no API key is provided
        return _fallback_report(current_report, fixed_issues, new_issues)
        
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating AI report: {e}")
        return _fallback_report(current_report, fixed_issues, new_issues)


def _fallback_report(current, fixed, new):
    report = "<h2>Weekly Website Health Report</h2>"
    
    report += "<h3>Issues Fixed</h3>"
    if fixed:
        for f in fixed: report += f"<p>{f}</p>"
    else:
        report += "<p>No explicitly fixed issues detected.</p>"
        
    report += "<h3>New Issues Identified</h3>"
    if new:
        for n in new: report += f"<p>{n}</p>"
    else:
        report += "<p>No explicitly new issues detected.</p>"
        
    report += "<h3>🔴 Critical Issues Requiring Attention</h3>"
    if current.get("broken_links"):
        report += "<ul>"
        for link in current["broken_links"]:
             report += f"<li>Broken Link: {link.get('url')} (Status: {link.get('status')})</li>"
        report += "</ul>"
    else:
        report += "<p>No critical issues found.</p>"
        
    return report
