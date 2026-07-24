import requests
from bs4 import BeautifulSoup
import json
import os
import time  # 【关键】这里补充了 time 模块，用于重试等待

# 目标网址
base_url = "https://ggzyjy.shandong.gov.cn/search.jspx?q=%25E4%25B8%25AD%25E6%25A0%2587%25E5%2585%25AC%25E5%2591%258A"

# 请求头
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}

def parse_list(page_url):
    """
    解析山东省公共资源交易网的搜索结果页，并增加了重试机制
    """
    items = []
    max_retries = 3  # 最多重试3次
    
    for attempt in range(max_retries):
        try:
            print("[INFO] 正在尝试连接... (第 " + str(attempt + 1) + " 次)")
            resp = requests.get(page_url, headers=headers, timeout=20) 
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            for li_tag in soup.find_all('li'):
                a_tag = li_tag.find('a')
                if a_tag and a_tag.get('title'):
                    title = a_tag['title']
                    href = a_tag['href']
                    if not href.startswith('http'):
                        href = 'https://ggzyjy.shandong.gov.cn' + href
                    items.append({'title': title, 'url': href})
                    print("[+] 发现项目: " + title)
            
            print("[INFO] 本页共发现 " + str(len(items)) + " 条记录")
            break  # 如果成功，就跳出重试循环
            
        except Exception as e:
            print("[ERROR] 第 " + str(attempt + 1) + " 次尝试失败: " + str(e))
            if attempt < max_retries - 1:
                print("[INFO] 2秒后准备重试...")
                time.sleep(2)  # 等待2秒再重试
            else:
                print("[ERROR] 已达到最大重试次数，放弃连接。")
        
    return items

if __name__ == '__main__':
    print("[INFO] 正在启动爬虫...")
    results = parse_list(base_url)
    
    if results:
        os.makedirs("data", exist_ok=True)
        with open("data/bids_2025.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("[DONE] 成功保存数据到 data/bids_2025.json")
    else:
        print("[WARN] 未抓取到任何数据")
