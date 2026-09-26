import requests
print("Probando endpoints...")
for url in [
    "https://siradig.onrender.com/api/receipts/pending/",
    "https://siradig.onrender.com/api/receipts/",
    "https://siradig.onrender.com/receipts/pending/",
    "https://siradig.onrender.com/"
]:
    try:
        r = requests.get(url, timeout=5)
        print(url, "-> status:", r.status_code, "len:", len(r.text))
    except Exception as e:
        print(url, "-> ERROR:", e)
