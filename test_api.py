import requests

api_key = "5cea06e8-2065-09e9-09f4-10ac50da9693"
domain = "amipi.com"

# Backlinks
url1 = "https://api.seranking.com/v1/backlinks/summary"
headers = {"Authorization": f"Token {api_key}"}
resp1 = requests.get(url1, headers=headers, params={"target": domain})
print("Backlinks Status:", resp1.status_code)
print("Backlinks JSON:", resp1.text[:500])

# Traffic
url2 = "https://api.seranking.com/v1/domain/overview/db"
resp2 = requests.get(url2, headers=headers, params={"domain": domain, "source": "us"})
print("Traffic Status:", resp2.status_code)
print("Traffic JSON:", resp2.text[:500])
