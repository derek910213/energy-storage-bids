import requests
from bs4 import BeautifulSoup
import re

url = "https://news.bjx.com.cn/zb/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://news.bjx.com.cn/"
}

print("[INFO] 正在请求列表页...")
resp = requests.get(url, headers=headers, timeout=15)
resp.encoding = 'utf-8'

print(f"[DEBUG] 状态码: {resp.status_code}")
print(f"[DEBUG] 网页前300字: {resp.text[:300]}")
