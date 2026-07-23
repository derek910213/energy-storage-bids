import requests
from bs4 import BeautifulSoup
import time
import re

# 请求头伪装，防止被网站拦截
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}

def parse_list(page_url):
    """
    解析列表页，提取所有储能相关招标条目的链接和标题
    """
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        items = []
        # 根据你提供的真实HTML，列表项是带title属性的<a>标签
        for a_tag in soup.find_all('a', href=True, title=True):
            title = a_tag.get('title', '').strip()
            href = a_tag['href']
            
            # 只保留包含"储能"关键词的条目
            if '储能' in title:
                # 确保链接是完整URL
                if not href.startswith('http'):
                    href = 'https://news.bjx.com.cn' + href
                items.append({'title': title, 'url': href})
                
        return items
    except Exception as e:
        print(f"[ERROR] 列表页解析失败: {e}")
        return []

def parse_detail(detail_url):
    """
    解析详情页，提取标题和正文中的中标信息
    """
    try:
        resp = requests.get(detail_url, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 提取详情页标题（你提供的<h1>标签）
        h1_tag = soup.find('h1')
        title = h1_tag.get_text(strip=True) if h1_tag else ''
        
        # 尝试从正文中提取中标人和金额（通用策略）
        content_div = soup.find('div', class_=re.compile(r'article|content|detail', re.I))
        text = content_div.get_text('\n', strip=True) if content_div else soup.get_text('\n', strip=True)
        
        candidate = ''
        amount = ''
        for line in text.split('\n'):
            line = line.strip()
            if ('中标候选人' in line or '中标人' in line) and not candidate:
                candidate = line.split('：')[-1].split(':')[-1].strip()
            if ('中标金额' in line or '投标报价' in line) and not amount:
                amount = line.split('：')[-1].split(':')[-1].strip()
        
        return {
            'title': title,
            'candidate': candidate,
            'amount': amount,
            'url': detail_url
        }
    except Exception as e:
        print(f"[ERROR] 详情页解析失败 {detail_url}: {e}")
        return None

# === 主执行逻辑（替换你原有scrape.py的主函数部分）===
if __name__ == '__main__':
    all_records = []
    base_url = "https://news.bjx.com.cn/zb/"  # 如有分页，后续可拼接页码
    
    print("[INFO] 正在爬取列表页...")
    items = parse_list(base_url)
    print(f"[INFO] 发现 {len(items)} 条储能相关记录")
    
    for idx, item in enumerate(items[:10], 1):  # 先测试前10条，避免触发反爬
        print(f"[INFO] 正在爬取第 {idx} 条: {item['title'][:30]}...")
        detail = parse_detail(item['url'])
        if detail:
            all_records.append(detail)
        time.sleep(2)  # ⚠️ 必须加延迟！北极星对频繁访问敏感
        
    print(f"[DONE] 共采集 {len(all_records)} 条有效记录")
    # 后续可添加保存CSV/JSON的代码
