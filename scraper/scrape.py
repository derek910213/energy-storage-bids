import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime, timedelta

# ========== 配置区 ==========
# 中国政府采购网 - 搜索接口
SEARCH_URL = "http://search.ccgp.gov.cn/bxsearch"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 搜索参数
params = {
    "searchtype": "1",
    "page_index": "1",
    "bidSort": "0",
    "buyerName": "",
    "projectId": "",
    "pinMu": "0",
    "bidType": "1",        # 1=招标公告
    "dbselect": "bidx",
    "kw": "",              # 关键词（留空=全部）
    "start_time": "2026:07:01",
    "end_time": "2026:07:24",
    "timeType": "2",
    "displayZone": "",
    "zoneId": "",
    "pppStatus": "0",
    "agentName": "",
}


def test_connectivity():
    """测试网络连通性"""
    test_urls = [
        ("中国政府采购网", "http://www.ccgp.gov.cn"),
        ("搜索接口", "http://search.ccgp.gov.cn"),
    ]
    for name, url in test_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            print(f"[✓] {name} 连接成功 (状态码: {resp.status_code})")
            return True
        except Exception as e:
            print(f"[✗] {name} 连接失败: {e}")
    return False


def fetch_page(page_num=1):
    """抓取指定页码的招标公告列表"""
    items = []
    params["page_index"] = str(page_num)

    try:
        print(f"[INFO] 正在抓取第 {page_num} 页...")
        resp = requests.get(SEARCH_URL, params=params, headers=headers, timeout=30)
        resp.encoding = 'utf-8'

        if resp.status_code != 200:
            print(f"[ERROR] HTTP 状态码: {resp.status_code}")
            return items

        soup = BeautifulSoup(resp.text, 'html.parser')

        # 查找搜索结果列表
        result_list = soup.find('ul', class_='vT-srch-result-list-bid')
        if not result_list:
            # 尝试备选选择器
            result_list = soup.find('ul', class_='vT-srch-result-list')
        if not result_list:
            print(f"[WARN] 第 {page_num} 页未找到结果列表")
            # 打印页面标题用于调试
            title_tag = soup.find('title')
            print(f"[DEBUG] 页面标题: {title_tag.text if title_tag else '无'}")
            # 保存HTML用于调试
            debug_dir = "data/debug"
            os.makedirs(debug_dir, exist_ok=True)
            with open(f"{debug_dir}/page_{page_num}.html", "w", encoding="utf-8") as f:
                f.write(resp.text)
            print(f"[DEBUG] 已保存页面到 {debug_dir}/page_{page_num}.html")
            return items

        for li in result_list.find_all('li'):
            a_tag = li.find('a')
            if not a_tag:
                continue

            title = a_tag.get_text(strip=True)
            href = a_tag.get('href', '')

            # 提取日期
            date_span = li.find('span')
            pub_date = date_span.get_text(strip=True) if date_span else ''

            # 提取摘要
            summary_p = li.find('p')
            summary = summary_p.get_text(strip=True) if summary_p else ''

            if title and href:
                items.append({
                    'title': title,
                    'url': href,
                    'date': pub_date,
                    'summary': summary[:200]
                })
                print(f"  [+] {title[:50]}...")

        print(f"[INFO] 第 {page_num} 页获取 {len(items)} 条记录")

    except Exception as e:
        print(f"[ERROR] 抓取第 {page_num} 页失败: {e}")

    return items


def main():
    print("=" * 50)
    print("[INFO] 中国政府采购网 - 招标公告爬虫")
    print("=" * 50)

    # 第一步：测试连通性
    print("\n[STEP 1] 测试网络连通性...")
    if not test_connectivity():
        print("[FATAL] 无法连接到目标网站，请检查网络环境。")
        print("[TIP] 如果在 GitHub Actions 中运行，可能是海外服务器无法访问 .gov.cn 网站。")
        return

    # 第二步：抓取数据（抓3页）
    print("\n[STEP 2] 开始抓取数据...")
    all_items = []
    total_pages = 3

    for page in range(1, total_pages + 1):
        items = fetch_page(page)
        all_items.extend(items)
        if not items:
            print(f"[INFO] 第 {page} 页无数据，停止翻页。")
            break
        if page < total_pages:
            time.sleep(2)  # 礼貌延迟

    # 第三步：保存结果
    print(f"\n[STEP 3] 保存结果...")
    os.makedirs("data", exist_ok=True)

    if all_items:
        output_file = "data/bids_ccgp.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_items, f, ensure_ascii=False, indent=2)
        print(f"[DONE] ✅ 成功抓取 {len(all_items)} 条数据 → {output_file}")
    else:
        print("[WARN] ❌ 未抓取到任何数据。")
        print("[TIP] 请检查 data/debug/ 目录下的 HTML 文件以分析页面结构。")


if __name__ == '__main__':
    main()
