import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
BASE_URL = "https://news.bjx.com.cn/topics/chunengzhongbiao/"


def get_article_list():
    """抓取列表页，筛选2025年及以后的储能中标公告"""
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
        print(f"列表页响应状态码: {resp.status_code}")
        # 打印前500字符，便于调试
        print(f"列表页内容前500字: {resp.text[:500]}")
    except Exception as e:
        print(f"请求列表页失败：{e}")
        return []

    soup = BeautifulSoup(resp.text, 'lxml')
    articles = []

    # 尝试多种常见的列表选择器
    article_items = (
        soup.select('div.list_left li') or           # 旧版结构
        soup.select('div.list_right li') or          # 备用结构
        soup.select('ul.list li') or                 # 通用列表
        soup.select('div.list li') or                # 无类名的列表
        soup.select('.list-con li') or               # 常见类名
        soup.select('.list_box li') or               # 另一种常见类名
        soup.select('div.article-list li') or        # 文章列表
        soup.select('div.news_list li')              # 新闻列表
    )

    print(f"找到 {len(article_items)} 个列表项")

    for item in article_items:
        a_tag = item.find('a')
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)
        link = a_tag.get('href', '')
        if not link:
            continue

        # 补全链接
        if not link.startswith('http'):
            if link.startswith('/'):
                link = 'https://chuneng.bjx.com.cn' + link
            else:
                link = 'https://chuneng.bjx.com.cn/' + link

        # 提取日期（尝试多种常见类名）
        date_span = (
            item.find('span', class_='date') or
            item.find('span', class_='time') or
            item.find('span', class_='list_time') or
            item.find('em') or
            item.find('i')
        )
        date_str = date_span.get_text(strip=True) if date_span else ''

        # 筛选2025年及以后的
        is_2025 = False
        if date_str and ('2025' in date_str or '2026' in date_str):
            is_2025 = True
        elif '2025' in title or '25年' in title:
            is_2025 = True
            date_str = '2025'  # 无法提取日期时用年份标记

        if is_2025:
            articles.append({
                'title': title,
                'link': link,
                'date': date_str if date_str else '2025'
            })
            print(f"  收录: {title[:40]}... | 日期: {date_str}")

    return articles


def parse_detail(article):
    """进入详情页，提取中标信息"""
    try:
        resp = requests.get(article['link'], headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
    except Exception as e:
        print(f"请求详情页失败 {article['link'][:60]}: {e}")
        return None

    soup = BeautifulSoup(resp.text, 'lxml')

    # 查找正文区域（尝试多种可能的选择器）
    content_div = (
        soup.find('div', class_='article-body') or
        soup.find('div', class_='article-content') or
        soup.find('div', class_='article_con') or
        soup.find('div', class_='content') or
        soup.find('div', class_='article') or
        soup.find('article')
    )

    if not content_div:
        print(f"  未找到正文区域: {article['link'][:60]}")
        return None

    text = content_div.get_text('\n', strip=True)

    # ----- 提取中标单位 -----
    winner = '未知'
    win_patterns = [
        r'中标(?:人|单位|候选人)[：:]\s*(\S+?)(?:[。，；\s]|$)',
        r'中标(?:人|单位|候选人)(?:名称)?[：:]\s*(\S+?)(?:[。，；\s]|$)',
        r'(?:确定|拟确定)(\S+?公司)为中标',
        r'第一中标候选人[：:]\s*(\S+?)(?:[。，；\s]|$)',
    ]
    for pattern in win_patterns:
        match = re.search(pattern, text)
        if match:
            winner = match.group(1).strip()
            break

    # ----- 提取中标金额 -----
    amount = '未知'
    money_patterns = [
        r'中标(?:金额|价|总价)[：:]\s*([\d,.]+)\s*万[元]?',
        r'投标报价[：:]\s*([\d,.]+)\s*万[元]?',
        r'中标金额[：:]\s*([\d,.]+)\s*元',
        r'(?:金额|报价)[：:]\s*([\d,.]+)\s*万[元]?',
    ]
    for pattern in money_patterns:
        match = re.search(pattern, text)
        if match:
            num = match.group(1)
            # 判断单位是元还是万元
            if '元' in match.group(0) and '万元' not in match.group(0):
                amount = f"{float(num.replace(',', ''))/10000:.2f}万元"
            else:
                amount = f"{num}万元"
            break

    # ----- 提取参与投标单位 -----
    participants = []
    part_match = re.search(
        r'(?:投标人|参与投标的单位|投标单位|投标申请人|递交投标文件的单位)[：:]\s*([\s\S]+?)(?=\n\s*(?:招标人|联系方式|$)|。\n)',
        text
    )
    if part_match:
        raw = part_match.group(1)
        # 分割并清洗
        names = re.split(r'[、，,;\n]', raw)
        for name in names:
            name = name.strip().rstrip('。，,;')
            if name and ('公司' in name or '集团' in name) and len(name) < 80:
                participants.append(name)

    # 如果上面没找到，尝试匹配带编号的列表
    if not participants:
        for li in content_div.find_all(['li', 'p', 'div']):
            txt = li.get_text(strip=True)
            # 匹配 "1.XX公司" 或 "1、XX公司" 格式
            if re.match(r'\d+[\.、,）)]\s*\S+公司', txt) and len(txt) < 80:
                name = re.sub(r'^\d+[\.、,）)]\s*', '', txt)
                participants.append(name)

    # 去重
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
    print(f"\n总共找到 {len(articles)} 篇2025年后的文章")

    new_data = []
    for i, art in enumerate(articles[:30]):  # 增加抓取数量到30篇
        print(f"\n处理第 {i+1}/{min(len(articles), 30)} 篇: {art['title'][:40]}")
        detail = parse_detail(art)
        if detail:
            print(f"  中标单位: {detail['winner']} | 金额: {detail['amount']}")
            new_data.append(detail)
        else:
            print(f"  解析失败，跳过")
        time.sleep(3)  # 增加延时，避免反爬

    # 读取已有数据，合并去重
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            old_data = json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        old_data = []

    old_links = {item['link'] for item in old_data}
    added = 0
    for item in new_data:
        if item['link'] not in old_links:
            old_data.insert(0, item)
            added += 1

    # 只保留最近500条
    old_data = old_data[:500]

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(old_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"本次新增 {added} 条记录，当前总数据 {len(old_data)} 条")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
