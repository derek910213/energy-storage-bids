from curl_cffi import requests
from bs4 import BeautifulSoup
import json, re, time
from datetime import datetime

BASE_URL = "https://news.bjx.com.cn/topics/chunengzhongbiao/" 

def get_article_list():
    try:
        resp = requests.get(BASE_URL, impersonate="chrome110", timeout=15)
        resp.encoding = 'utf-8'
        print(f"状态码: {resp.status_code}")
        print(f"页面长度: {len(resp.text)}")
    except Exception as e:
        print(f"请求失败：{e}")
        return []

    soup = BeautifulSoup(resp.text, 'lxml')
    articles = []
    items = []

    # 1. 尝试已知的选择器
    selectors = [
        'div.list_left li',
        'div.list_right li',
        'ul.list li',
        'div.newslist li',
        'div.article-list li',
        'div.list_box li',
        '.list-con li',
        '.list li',
    ]
    for sel in selectors:
        items = soup.select(sel)
        if items:
            print(f"使用选择器: {sel}，找到 {len(items)} 个列表项")
            break

    # 2. 如果都没找到，启用通用链接提取
    if not items:
        print("未匹配到专用列表项，启用通用链接提取...")
        all_a = soup.find_all('a', href=True)
        print(f"调试：页面中共有 {len(all_a)} 个链接")
        # 打印前30个链接，方便我们分析
        for i, a in enumerate(all_a[:30]):
            href = a['href']
            title = a.get_text(strip=True)[:60]
            print(f"  [{i+1}] {title}  -> {href[:100]}")
        # 过滤出可能的文章链接：href 包含 /html/ 且标题非空
        candidate = []
        for a in all_a:
            href = a.get('href', '')
            title = a.get_text(strip=True)
            if not title:
                continue
            # 常见文章链接格式
            if '/html/' in href and title:
                candidate.append(a)
        print(f"过滤后得到 {len(candidate)} 个候选文章链接")
        items = candidate

    # 3. 从 items 中提取 title, link, date
    for item in items:
        # 如果是 a 标签本身（通用模式），直接取
        if item.name == 'a':
            a_tag = item
        else:
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

        # 提取日期
        date_str = ''
        if item.name != 'a':
            date_span = (
                item.find('span', class_='date') or
                item.find('span', class_='time') or
                item.find('span', class_='list_time') or
                item.find('em') or
                item.find('i')
            )
            if date_span:
                date_str = date_span.get_text(strip=True)
        # 如果日期中没有年份，尝试从文本中提取
        if not date_str:
            # 简单的年份检测
            if '2025' in title or '2026' in title:
                date_str = '2025'
            else:
                date_str = datetime.now().strftime('%Y-%m-%d')  # 兜底用当天

        # 只收集2025年及以后的
        if '2025' in date_str or '2026' in date_str or '2025' in title:
            articles.append({'title': title, 'link': link, 'date': date_str})

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
    print(f"共筛选出 {len(articles)} 篇2025后文章")
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
