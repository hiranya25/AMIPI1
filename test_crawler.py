from crawler import WebsiteCrawler
import json

def test():
    url = "https://amipi.com"
    print(f"Starting test crawl for: {url}")
    crawler = WebsiteCrawler(url)
    crawler.crawl(max_depth=1)  # Using max_depth=1 to keep the test quick
    
    report = crawler.get_report()
    print("\n--- Crawl Results ---")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    test()
