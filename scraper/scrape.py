import requests
from bs4 import BeautifulSoup
import json
import os

# 目标网址：中国招标投标公共服务平台的中标候选人公示列表
base_url = "https://www.cebpubservice.com/candidatebulletin"

# 请求头
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}

def parse_list(page_url):
    """
    解析目标列表页，并增加了重试机制
    """
    items = []
    max_retries = 3  # 最多重试3次
    
    for attempt in range(max_retries):
        try:
            print(f"[INFO] 正在尝试连接... (第 {attempt + 1} 次)")
            resp = requests.get(page_url, headers=headers, timeout=20) 
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 查找所有公告列表项
            # 根据网页结构，公告列表在一个id为"bulletinList"的div中
            news_div = soup.find('div', id='bulletinList')
            if not news_div:
                print("[ERROR] 未找到公告列表容器 (id='bulletinList')")
                break # 如果找不到容器，直接跳出循环

            for li_tag in news_div.find_all('li'):
                a_tag = li_tag.find('a')
                if a_tag:
                    title = a_tag.get('title', '无标题')
                    href = a_tag['href']
                    # 拼接完整URL
                    if not href.startswith('http'):
                        href = 'https://www.cebpubservice.com' + href
                    items.append({'title': title, 'url': href})
                    print(f"[+] 发现项目: {title}")
            
            print(f"[INFO] 本页共发现 {len(items)} 条记录")
            break # 如果成功，就跳出重试循环
            
        except Exception as e:
            print(f"[ERROR] 第 {attempt + 1} 次尝试失败: {e}")
            if attempt < max_retries - 1:
                print("[INFO] 2秒后准备重试...")
                time.sleep(2) # 等待2秒再试
            else:
                print("[ERROR] 已达到最大重试次数，放弃连接。")
        
    return items

if __name__ == '__main__':
    print("[INFO] 正在启动爬虫...")
    results = parse_list(base_url)
    
    if results:
        os.makedirs("data", exist_ok=True)
        with open("data/bids_2026.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[DONE] 成功抓取 {len(results)} 条数据并保存到 data/bids_2026.json")
    else:
        print("[WARN] 未抓取到任何数据，请检查网络连接和页面结构。")
