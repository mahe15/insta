import urllib.request, json, http.cookiejar
from pathlib import Path

key = Path("data/web/access-key").read_text().strip()
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. Login
req1 = urllib.request.Request(
    "http://127.0.0.1:8788/api/session",
    data=json.dumps({"key": key}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
res1 = json.loads(opener.open(req1).read().decode("utf-8"))
csrf = res1["csrf"]

# 2. Get carousels
req_car = urllib.request.Request(
    "http://127.0.0.1:8788/api/carousels",
    headers={"x-csrf-token": csrf}
)
carousels = json.loads(opener.open(req_car).read().decode("utf-8"))
print(f"Carousels list returned {len(carousels)} jobs.")
if carousels:
    print(f"Sample carousel job prompt field: '{carousels[0].get('prompt', '')}'")

print("LIVE VERIFICATION COMPLETE!")
