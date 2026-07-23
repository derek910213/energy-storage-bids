import requests
from bs4 import BeautifulSoup
import json, re, time
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}
BASE_URL = "https://chuneng.bjx.com.cn/zhongbiao/"

def get_article_list():
    """抓取列表页，只取2025年及以后的标题链接"""
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
    except Exception as e:
        print(f"请求列表页失败：{e}")
        return []
    soup = BeautifulSoup(resp.text, 'lxml')
    articles = []
    # 北极星中标频道常见结构：div.list_left 下的 li 标签
    for li in soup.select('div.list_left li'):
        a_tag = li.find('a')
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        link = a_tag.get('href', '')
        if not link.startswith('http'):
            link = 'https://chuneng.bjx.com.cn' + link
        # 提取日期
        date_span = li.find('span', class_='date')
        if not date_span:
            date_span = li.find('span')
        date_str = ''
        if date_span:
            date_str = date_span.get_text(strip=True)
        # 只取2025年之后的（包含2025）
        if date_str and date_str >= '2025-01-01':
            articles.append({'title': title, 'link': link, 'date': date_str})
        else:
            # 如果没有日期或日期早于2025，也尝试用标题判断（备用）
            if '2025' in title or '25年' in title:
                articles.append({'title': title, 'link': link, 'date': '2025'})
    return articles

def parse_detail(article):
    """进入详情页，提取中标单位、金额、参与单位"""
    try:
        resp = requests.get(article['link'], headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
    except Exception as e:
        print(f"请求详情页失败 {article['link']}: {e}")
        return None
    soup = BeautifulSoup(resp.text, 'lxml')
    # 正文区域（北极星常见 class）
    content_div = soup.find('div', class_='article-body') or soup.find('div', class_='article-content')
    if not content_div:
        print(f"未找到正文：{article['link']}")
        return None
    text = content_div.get_text('\n', strip=True)

    # 1. 中标单位
    winner = '未知'
    win_match = re.search(r'中标(?:人|单位|候选人)[：:]\s*(\S+)', text)
    if win_match:
        winner = win_match.group(1)

    # 2. 中标金额（万元）
    amount = '未知'
    money_match = re.search(r'中标(?:金额|价)[：:]\s*([\d,.]+)\s*(?:万[元]?)?', text)
    if money_match:
        amount = money_match.group(1) + '万元'

    # 3. 参与投标单位
    participants = []
    # 尝试多种常见句式
    part_match = re.search(r'(?:投标人|参与投标的单位|投标单位)[：:]\s*([\s\S]+?)(?=\n\s*招标人|\n\s*$|。\n)', text)
    if part_match:
        raw = part_match.group(1)
        # 分割并清洗
        names = re.split(r'[、，,;\n]', raw)
        for name in names:
            name = name.strip()
            if name and '公司' in name and len(name) < 50:
                participants.append(name)
    # 如果没找到，尝试找列表项
    if not participants:
        for li in content_div.find_all('li'):
            txt = li.get_text(strip=True)
            if '公司' in txt and len(txt) < 50:
                participants.append(txt)

    # 去掉重复
    participants = list(dict.fromkeys(participants))

    return {
        'title': soup.title.string.strip() if soup.title else article['title'],
        'winner': winner,
        'amount': amount,
        'participants': participants,
        'link': article['link'],
        'date': article.get('date', datetime.now().strftime('%Y-%m-%d'))
    }

def main():
    articles = get_article_list()
    print(f"找到 {len(articles)} 篇2025年后的文章")
    new_data = []
    for art in articles[:20]:   # 每次最多抓20篇，避免时间过长
        detail = parse_detail(art)
        if detail:
            new_data.append(detail)
            print(f"已处理：{detail['title'][:30]}...")
        time.sleep(2)   # 礼貌等待

    # 读取已有数据，合并并去重（按链接去重）
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            old_data = json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        old_data = []

    old_links = {item['link'] for item in old_data}
    for item in new_data:
        if item['link'] not in old_links:
            old_data.insert(0, item)   # 新数据放在最前面

    # 只保留最近500条，防止文件过大
    old_data = old_data[:500]
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(old_data, f, ensure_ascii=False, indent=2)
    print(f"更新完成，当前总数据 {len(old_data)} 条")

if __name__ == '__main__':
    main()
