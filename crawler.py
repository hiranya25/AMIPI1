import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

class WebsiteCrawler:
    def __init__(self, start_url):
        self.start_url = start_url
        self.domain = urlparse(start_url).netloc
        self.visited = set()
        self.issues = {
            "broken_links": [],
            "missing_alt_tags": [],
            "missing_metadata": [],
            "slow_pages": []
        }

    def crawl(self, url=None, depth=0, max_depth=2):
        if url is None:
            url = self.start_url

        if url in self.visited or depth > max_depth:
            return

        self.visited.add(url)
        print(f"Crawling: {url}")

        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            end_time = time.time()
            load_time = end_time - start_time

            if response.status_code >= 400:
                self.issues["broken_links"].append({"url": url, "status": response.status_code})
                return

            if load_time > 3.0: # Arbitrary threshold for slow page
                self.issues["slow_pages"].append({"url": url, "load_time_seconds": round(load_time, 2)})
            
            # Only parse HTML pages
            if "text/html" not in response.headers.get("Content-Type", ""):
                return

            soup = BeautifulSoup(response.text, "html.parser")
            self._check_metadata(url, soup)
            self._check_images(url, soup)
            
            # Find and crawl links
            for link in soup.find_all("a", href=True):
                href = link.get("href")
                full_url = urljoin(url, href)
                
                # Check if it's the same domain
                if urlparse(full_url).netloc == self.domain:
                    self.crawl(full_url, depth + 1, max_depth)
                else:
                    # External link check (shallow)
                    self._check_external_link(full_url)

        except requests.RequestException as e:
            self.issues["broken_links"].append({"url": url, "error": str(e)})

    def _check_metadata(self, url, soup):
        title = soup.find("title")
        description = soup.find("meta", attrs={"name": "description"})
        
        if not title or not title.string.strip():
            self.issues["missing_metadata"].append({"url": url, "type": "Missing Title"})
            
        if not description or not description.get("content", "").strip():
            self.issues["missing_metadata"].append({"url": url, "type": "Missing Meta Description"})

    def _check_images(self, url, soup):
        for img in soup.find_all("img"):
            if not img.get("alt"):
                src = img.get("src", "Unknown Source")
                self.issues["missing_alt_tags"].append({"page_url": url, "image_src": src})

    def _check_external_link(self, url):
        if url in self.visited:
            return
        self.visited.add(url)
        try:
            # Use HEAD request for external links to save bandwidth
            response = requests.head(url, timeout=5)
            if response.status_code >= 400:
                self.issues["broken_links"].append({"url": url, "status": response.status_code, "type": "external"})
        except requests.RequestException:
             self.issues["broken_links"].append({"url": url, "error": "Connection Failed", "type": "external"})

    def get_report(self):
        return self.issues
