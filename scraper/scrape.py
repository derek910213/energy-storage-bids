import requests
from bs4 import BeautifulSoup
import json
import os
import time

# ================= 1. 配置区 =================
# 目标网址（目前为搜索“中标公告”的链接，建议后续替换为搜索“储能”的链接）
base_url = "https://ggzyjy.shandong.gov.cn/search.jspx?q=%25E4%25B8%25AD%25E6%25A0%2587%25E5%2585%25AC%25E5%2591%258A"

# 请求头伪装
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
}

# ================= 2. 解析函数 =================
def parse_list(page_url):
    """
    解析山东省公共资源交易网的搜索结果页
    """
    items = []
    try:
        resp = requests.get(page_url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 遍历页面中所有的 <li> 标签
        for li_tag in soup.find_all('li'):
            # 在每个 <li> 标签里找标题链接 <a>
            a_tag = li_tag.find('a')
            if a_tag and a_tag.get('title'): 
                title = a_tag['title']
                href = a_tag['href']
                
                # 确保链接是完整的URL
                if not href.startswith('http'):
                    href = 'https://ggzyjy.shandong.gov.cn' + href
                
                items.append({'title': title, 'url': href})
                print(f"[+] 发现项目: {title}")
                
        print(f"[INFO] 本页共发现 {len(items)} 条记录")
    except Exception as e:
        print(f"[ERROR] 列表页解析失败: {e}")
        
    return items

# ================= 3. 主运行逻辑 =================
if __name__ == '__main__':
    print("[INFO] 正在启动爬虫...")
    results = parse_list(base_url)
    
    # 自动创建 data 文件夹并保存为 JSON 文件
    if results:
        os.makedirs("data", exist_ok=True)
        with open("data/bids_2025.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
       print(f"[DONE] 成功保存 {len(results)} 条数据到 data/bids_2025.json")
