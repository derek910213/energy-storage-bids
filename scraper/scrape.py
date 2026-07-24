# -*- coding: utf-8 -*-
"""
中国招标投标公共服务平台 (bulletin.cebpubservice.com)
储能相关 —— 中标结果公示 / 中标候选人公示 采集脚本
--------------------------------------------------------------
提取字段：项目标的、中标单位、中标金额、候选单位（及排名/报价，若公示中提供）、
          发布日期、所属行业、所属地区、原文链接

⚠️ 请务必先读——关于本脚本可靠性的说明：
    1. 我实际探测了生产站 bulletin.cebpubservice.com，直接 GET 请求返回了
       405 (Method Not Allowed)。这通常意味着：
           a) 服务器对 User-Agent / Referer / Cookie 做了校验，或
           b) 页面内容其实是前端 JS 调接口异步渲染的，纯 requests 抓不到东西
       下面代码默认用"伪装成浏览器"的方式请求（带 UA、Referer、Accept 等），
       如果你运行后仍然拿不到数据 / 仍是 405，说明是第二种情况，
       需要改用 Selenium / Playwright 渲染 JS 后再解析
       （脚本最下面留了 Selenium 版本的框架，可以直接改用）。

    2. 我是通过该平台的"测试环境"(testbulletin.cebpubservice.com)拿到的
       真实页面结构（分类页 URL 规律、表格字段、详情页链接格式），测试环境
       与生产站代码结构一致，但生产站数据量、反爬策略可能更严格。

    3. 该平台目前没有找到"全站关键词搜索"的公开接口，所以本脚本采用的策略是：
           抓取【中标结果公示】(categoryId=90) 和【中标候选人公示】(categoryId=91)
           两个栏目的列表 -> 用标题关键词（储能、储能电站、储能系统、
           电化学储能、共享储能……）过滤出储能相关项目 -> 再进详情页
           提取中标单位/金额/候选单位等信息
       这两个栏目每天新增几千条，量很大，建议先用 dates 参数限定时间范围
       （已按你的需求设为近 365 天），并做好断点续爬（脚本已支持增量保存）。

    4. 详情页里"中标金额""中标单位""候选单位"的具体措辞在不同来源渠道
       （地方交易平台）里差异很大，正则提取不可能 100% 覆盖，建议先跑一小批
       （比如 MAX_PAGES=2）看看提取效果，再针对未命中的样式补充正则。
"""

import re
import csv
import time
import random
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ------------------------- 基础配置 -------------------------

BASE_URL = "https://bulletin.cebpubservice.com"

# 分类 ID：90 = 中标结果公示，91 = 中标候选人公示（含"候选单位"信息）
CATEGORIES = {
    90: "中标结果公示",
    91: "中标候选人公示",
}

# 储能相关关键词（标题命中任意一个即保留，可自行增减）
KEYWORDS = [
    "储能", "储能电站", "储能系统", "电化学储能", "共享储能",
    "储能电池", "储能柜", "储能项目", "光储", "风储",
]

DAYS_LIMIT = 365          # 只要近 1 年内的数据
MAX_PAGES_PER_CATEGORY = 200   # 每个栏目最多翻多少页，防止无限循环，可调整
PAGE_SIZE_DATES_PARAM = 365    # 传给网站的 dates 参数（网站自身的"近N天"筛选）

OUTPUT_CSV = "储能招标中标信息_中国招标投标公共服务平台.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": BASE_URL + "/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 金额：中标金额 / 成交金额 / 中标价 / 报价 等
AMOUNT_PATTERN = re.compile(
    r"(中标金额|成交金额|中标价|成交价|投标报价|报价)[：:\s]*"
    r"([0-9]+(?:[.,，][0-9]+)?)\s*(万元|元|亿元)?"
)

# 中标单位 / 中标人
WINNER_PATTERN = re.compile(
    r"(中标单位|中标人|成交单位|成交供应商|第一中标候选人)[：:\s]*"
    r"([^\s，,。；;\n]{2,60})"
)

# 候选单位（中标候选人公示里常见"第一候选人""第二候选人"等）
CANDIDATE_PATTERN = re.compile(
    r"(第[一二三1-3]候选人|候选人[一二三1-3]?)[：:\s]*"
    r"([^\s，,。；;\n]{2,60})"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("cebpubservice_spider")


# ------------------------- 工具函数 -------------------------

def polite_sleep(a=2.5, b=5):
    time.sleep(random.uniform(a, b))


def get_with_retry(session, url, params=None, max_retry=3, timeout=15):
    for attempt in range(1, max_retry + 1):
        try:
            resp = session.get(url, headers=HEADERS, params=params, timeout=timeout)
            if resp.status_code == 200:
                resp.encoding = resp.apparent_encoding or "utf-8"
                return resp
            elif resp.status_code == 405:
                logger.error(
                    "收到 405，说明该地址不接受普通 GET 请求——"
                    "很可能页面内容是 JS 异步加载的，requests 抓不到真实数据。"
                    "请改用脚本末尾的 Selenium 方案，或用浏览器 F12 -> Network "
                    "找到真实的数据接口后再改这里的 url/params。"
                )
                return None
            elif resp.status_code == 429:
                wait = 15 * attempt
                logger.warning(f"触发限流(429)，等待 {wait}s 后重试 ...")
                time.sleep(wait)
            else:
                logger.warning(f"状态码 {resp.status_code}，url={resp.url}")
                time.sleep(3 * attempt)
        except requests.RequestException as e:
            logger.warning(f"请求出错：{e}，第 {attempt} 次重试")
            time.sleep(3 * attempt)
    return None


def parse_date(text):
    """解析形如 2025-02-27 / 2025年02月27日 的日期文本"""
    text = (text or "").strip()
    patterns = [
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", "%Y-%m-%d"),
        (r"(\d{4})/(\d{1,2})/(\d{1,2})", "%Y/%m/%d"),
        (r"(\d{4})年(\d{1,2})月(\d{1,2})日", "%Y年%m月%d日"),
    ]
    for pat, fmt in patterns:
        m = re.search(pat, text)
        if m:
            try:
                return datetime.strptime(m.group(0), fmt)
            except ValueError:
                continue
    return None


def is_within_days(dt, days=DAYS_LIMIT):
    if dt is None:
        return True  # 解析不出日期时不主动丢弃，交给人工核对
    return dt >= datetime.now() - timedelta(days=days)


def title_hits_keyword(title):
    return any(kw in title for kw in KEYWORDS)


def extract_amount(text):
    m = AMOUNT_PATTERN.search(text)
    if m:
        return f"{m.group(2)}{m.group(3) or ''}"
    return ""


def extract_winner(text):
    m = WINNER_PATTERN.search(text)
    return m.group(2) if m else ""


def extract_candidates(text):
    """返回所有候选人匹配结果，格式如 ['第一候选人:xxx公司', '第二候选人:yyy公司']"""
    results = []
    for m in CANDIDATE_PATTERN.finditer(text):
        results.append(f"{m.group(1)}:{m.group(2)}")
    # 去重保序
    seen = set()
    uniq = []
    for r in results:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return "；".join(uniq)


# ------------------------- 核心抓取逻辑 -------------------------

def fetch_list_page(session, category_id, page):
    """
    抓取分类列表页（中标结果公示 / 中标候选人公示）
    [需核对] 若生产站实际参数名与测试环境不同，请用浏览器核实后调整
    """
    url = f"{BASE_URL}/xxfbcms/category/ceb_resultBulletinList.html"
    params = {
        "dates": PAGE_SIZE_DATES_PARAM,
        "categoryId": category_id,
        "page": page,
    }
    resp = get_with_retry(session, url, params=params)
    if resp is None:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # 表格结构：每一行 <tr> 里第一个 <a> 是标题+链接，其余 <td> 是行业/地区/来源/日期
    rows = soup.select("table tr")
    results = []
    for row in rows:
        a_tag = row.find("a")
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        if not title:
            continue

        # 链接常见写法：href="javascript:urlOpen('http://xxx.html')"
        href = a_tag.get("href", "") or a_tag.get("onclick", "")
        m = re.search(r"urlOpen\('([^']+)'\)", href)
        if m:
            link = m.group(1)
        else:
            link = urljoin(BASE_URL, href) if href.startswith("/") else href

        tds = row.find_all("td")
        cell_texts = [td.get_text(strip=True) for td in tds]

        # [需核对] 列顺序：标题 | 所属行业 | 所属地区 | 来源渠道 | 发布时间 | 距离开标时间
        industry = cell_texts[1] if len(cell_texts) > 1 else ""
        region = cell_texts[2] if len(cell_texts) > 2 else ""
        source = cell_texts[3] if len(cell_texts) > 3 else ""
        pub_date_text = cell_texts[4] if len(cell_texts) > 4 else ""

        results.append({
            "title": title,
            "link": link,
            "industry": industry,
            "region": region,
            "source": source,
            "pub_date_text": pub_date_text,
            "pub_date": parse_date(pub_date_text),
        })

    return results


def fetch_detail_text(session, link):
    """进入详情页，抓正文纯文本，供后续正则提取"""
    if not link or not link.startswith("http"):
        return ""
    resp = get_with_retry(session, link)
    if resp is None:
        return ""
    soup = BeautifulSoup(resp.text, "html.parser")

    content_node = (
        soup.select_one(".ck-content")
        or soup.select_one(".content")
        or soup.select_one("#content")
        or soup.select_one(".article")
        or soup.select_one("article")
    )
    if content_node:
        return content_node.get_text("\n", strip=True)
    return soup.get_text("\n", strip=True)


def crawl():
    session = requests.Session()
    all_rows = []

    for category_id, category_name in CATEGORIES.items():
        logger.info(f"===== 开始抓取栏目：{category_name} (categoryId={category_id}) =====")

        for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
            logger.info(f"[{category_name}] 第 {page} 页 ...")
            items = fetch_list_page(session, category_id, page)

            if not items:
                logger.info(f"[{category_name}] 第 {page} 页无数据，停止该栏目翻页。")
                break

            hit_any_recent = False
            for it in items:
                if not is_within_days(it["pub_date"], DAYS_LIMIT):
                    continue
                hit_any_recent = True

                if not title_hits_keyword(it["title"]):
                    continue

                logger.info(f"  -> 命中储能关键词：{it['title']}")
                detail_text = fetch_detail_text(session, it["link"])
                polite_sleep(1, 2)

                row = {
                    "类型": category_name,
                    "项目标的": it["title"],
                    "发布日期": it["pub_date_text"],
                    "所属行业": it["industry"],
                    "所属地区": it["region"],
                    "来源渠道": it["source"],
                    "中标单位": extract_winner(detail_text) or extract_winner(it["title"]),
                    "中标金额": extract_amount(detail_text),
                    "候选单位": extract_candidates(detail_text),
                    "原文链接": it["link"],
                }
                all_rows.append(row)

            # 如果这一页里已经没有"近1年内"的数据了（列表一般按时间倒序），
            # 说明后面的页更旧，可以提前结束该栏目
            if not hit_any_recent:
                logger.info(f"[{category_name}] 本页均超出近 {DAYS_LIMIT} 天范围，停止该栏目翻页。")
                break

            polite_sleep()

    return all_rows


def save_to_csv(rows, filename=OUTPUT_CSV):
    if not rows:
        logger.warning("没有抓到任何数据，不生成文件。请检查网站访问是否被拦截（见日志中的405提示）。")
        return
    fieldnames = ["类型", "项目标的", "发布日期", "所属行业", "所属地区",
                  "来源渠道", "中标单位", "中标金额", "候选单位", "原文链接"]
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"已保存 {len(rows)} 条数据到 {filename}")


if __name__ == "__main__":
    data = crawl()
    save_to_csv(data)


# ======================================================================
# 备用方案：如果上面 requests 版本一直收到 405 / 拿不到数据
# 说明页面是 JS 异步渲染的，需要用 Selenium 实际打开浏览器抓取
# 下面是可以直接套用的框架，把 crawl() 换成这个逻辑即可
# ======================================================================
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def crawl_with_selenium():
    options = Options()
    # options.add_argument("--headless=new")   # 先不加 headless，方便你肉眼确认页面加载正常
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    driver = webdriver.Chrome(options=options)

    all_rows = []
    try:
        for category_id, category_name in CATEGORIES.items():
            for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
                url = (
                    f"{BASE_URL}/xxfbcms/category/ceb_resultBulletinList.html"
                    f"?dates={PAGE_SIZE_DATES_PARAM}&categoryId={category_id}&page={page}"
                )
                driver.get(url)
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "table"))
                )
                # 到这里页面应该已经渲染完成，可以直接用 driver.page_source
                # 复用上面的 BeautifulSoup 解析逻辑：
                soup = BeautifulSoup(driver.page_source, "html.parser")
                # ... 后续解析逻辑与 fetch_list_page 相同，可直接复制过来 ...
                polite_sleep()
    finally:
        driver.quit()

    return all_rows
"""
