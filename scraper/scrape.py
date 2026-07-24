import requests
import json
import os
import time

# 全国公共资源交易平台 - 交易信息 API 接口
api_url = "https://deal.ggzy.gov.cn/ds/deal/dealList_find.jsp"

# 请求头（模拟浏览器）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://deal.ggzy.gov.cn/ds/deal/dealList.jsp",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest"
}

# POST 请求参数
payload = {
    "TIMEBEGIN_SHOW": "2026-07-01",
    "TIMEEND_SHOW": "2026-07-24",
    "TIMEBEGIN": "2026-07-01",
    "TIMEEND": "2026-07-24",
    "SOURCE_TYPE": "1",
    "DEAL_TIME": "02",
    "DEAL_CLASSIFY": "01",
    "DEAL_STAGE": "0101",
    "DEAL_PROVINCE": "0",
    "DEAL_CITY": "0",
    "PAESSION_KEY": "",
    "CORP_NAME": "",
    "CATEGORY_CODE": "",
    "pageNo": "1",
    "pageSize": "15"
}

def fetch_data():
    """通过 API 接口获取招标公告数据"""
    items = []
    max_retries = 3

    for attempt in range(max_retries):
        try:
            print(f"[INFO] 正在尝试连接 API... (第 {attempt + 1} 次)")
            resp = requests.post(api_url, data=payload, headers=headers, timeout=30)
            resp.encoding = 'utf-8'

            # 尝试解析 JSON
            data = resp.json()

            # 根据返回结构提取数据
            if isinstance(data, dict):
                # 尝试常见的返回字段名
                records = data.get('data', data.get('result', data.get('list', [])))
                if isinstance(records, dict):
                    records = records.get('list', records.get('records', []))
            elif isinstance(data, list):
                records = data
            else:
                records = []

            if not records:
                print(f"[WARN] API 返回数据为空，原始响应前200字符: {str(data)[:200]}")
                break

            for item in records:
                title = item.get('title', item.get('name', item.get('projectName', '无标题')))
                url = item.get('url', item.get('link', ''))
                pub_date = item.get('publishDate', item.get('timeShow', item.get('date', '')))
                items.append({
                    'title': title,
                    'url': url,
                    'date': pub_date
                })
                print(f"[+] 发现项目: {title}")

            print(f"[INFO] 本次共获取 {len(items)} 条记录")
            break

        except requests.exceptions.JSONDecodeError:
            print(f"[ERROR] 第 {attempt + 1} 次：返回内容不是 JSON")
            print(f"[DEBUG] 响应前300字符: {resp.text[:300]}")
        except Exception as e:
            print(f"[ERROR] 第 {attempt + 1} 次尝试失败: {e}")

        if attempt < max_retries - 1:
            print("[INFO] 3秒后重试...")
            time.sleep(3)

    return items


if __name__ == '__main__':
    print("[INFO] 正在启动爬虫（API 模式）...")
    results = fetch_data()

    if results:
        os.makedirs("data", exist_ok=True)
        with open("data/bids_2026.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[DONE] 成功抓取 {len(results)} 条数据 → data/bids_2026.json")
    else:
        print("[WARN] 未抓取到数据。")
        print("[TIP] 如果 API 地址失效，请运行以下调试命令查看返回内容：")
        print("      curl -X POST https://deal.ggzy.gov.cn/ds/deal/dealList_find.jsp")
