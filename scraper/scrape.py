from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime

# 注意：这里不再用 requests，而是 curl_cffi.requests，它能模拟浏览器的 TLS 指纹
BASE_URL = "https://chuneng.bjx.com.cn/zhongbiao/"

def get_article_list():
    try:
        # impersonate 参数模拟 Chrome 浏览器
        resp = requests.get(BASE_URL, impersonate="chrome110", timeout=15)
        resp.encoding = 'utf-8'
        print(f"状态码: {resp.status_code}")
        print(f"页面长度: {len(resp.text)}")
    except Exception as e:
        print(f"请求列表页失败：{e}")
        return []

    soup = BeautifulSoup(resp.text, 'lxml')
    articles = []

    # 尝试多种常见的列表选择器
    selectors = [
        'div.list_left li',
        'div.list_right li',
        'ul.list li',
        'div.list li',
        '.list-con li',
        '.list_box li',
        'div.article-list li',
        'div.news_list li'
    ]
    items = []
    for sel in selectors:
        items = soup.select(sel)
        if items:
            break

    print(f"找到 {len(items)} 个列表项")
    for item in items:
        a_tag = item.find('a')
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        link = a_tag.get('href', '')
        if not link:
            continue
        if not link.startswith('http'):
            if link.startswith('/'):
                link = 'https://chuneng.bjx.com.cn' + link
            else:
                link = 'https://chuneng.bjx.com.cn/' + link

        date_span = (
            item.find('span', class_='date') or
            item.find('span', class_='time') or
            item.find('span', class_='list_time') or
            item.find('em') or
            item.find('i')
        )
        date_str = date_span.get_text(strip=True) if date_span else ''

        if date_str and ('2025' in date_str or '2026' in date_str):
            articles.append({'title': title, 'link': link, 'date': date_str})
        elif '2025' in title or '25年' in title:
            articles.append({'title': title, 'link': link, 'date': '2025'})

    return articles

def parse_detail(article):
    try:
        resp = requests.get(article['link'], impersonate="chrome110", timeout=15)
        resp.encoding = 'utf-8'
    except Exception as e:
        print(f"详情页失败: {e}")
        return None

    soup = BeautifulSoup(resp.text, 'lxml')
    content_div = (
        soup.find('div', class_='article-body') or
        soup.find('div', class_='article-content') or
        soup.find('div', class_='article_con') or
        soup.find('div', class_='content') or
        soup.find('div', class_='article') or
        soup.find('article')
    )
    if not content_div:
        return None

    text = content_div.get_text('\n', strip=True)

    winner = '未知'
    for pat in [
        r'中标(?:人|单位|候选人)[：:]\s*(\S+?)(?:[。，；\s]|$)',
        r'第一中标候选人[：:]\s*(\S+?)(?:[。，；\s]|$)',
    ]:
        m = re.search(pat, text)
        if m:
            winner = m.group(1).strip()
            break

    amount = '未知'
    for pat in [
        r'中标(?:金额|价|总价)[：:]\s*([\d,.]+)\s*万[元]?',
        r'投标报价[：:]\s*([\d,.]+)\s*万[元]?',
    ]:
        m = re.search(pat, text)
        if m:
            amount = m.group(1) + '万元'
            break

    participants = []
    part_match = re.search(
        r'(?:投标人|参与投标的单位|投标单位)[：:]\s*([\s\S]+?)(?=\n\s*(?:招标人|联系方式|$)|。\n)',
        text
    )
    if part_match:
        names = re.split(r'[、，,;\n]', part_match.group(1))
        for n in names:
            n = n.strip().rstrip('。，,;')
            if n and ('公司' in n or '集团' in n) and len(n) < 80:
                participants.append(n)

    if not participants:
        for li in content_div.find_all(['li', 'p', 'div']):
            txt = li.get_text(strip=True)
            if re.match(r'\d+[\.、,）)]\s*\S+公司', txt) and len(txt) < 80:
                name = re.sub(r'^\d+[\.、,）)]\s*', '', txt)
                participants.append(name)

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
    print(f"共找到 {len(articles)} 篇")
    new_data = []
    for i, art in enumerate(articles[:30]):
        print(f"处理 {i+1}: {art['title'][:40]}")
        detail = parse_detail(art)
        if detail:
            new_data.append(detail)
        time.sleep(3)

    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            old_data = json.load(f)
    except:
        old_data = []

    old_links = {item['link'] for item in old_data}
    added = 0
    for item in new_data:
        if item['link'] not in old_links:
            old_data.insert(0, item)
            added += 1

    old_data = old_data[:500]
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(old_data, f, ensure_ascii=False, indent=2)

    print(f"\n新增 {added} 条，共 {len(old_data)} 条")

if __name__ == '__main__':
    main()
