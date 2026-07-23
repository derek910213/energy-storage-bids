import requests
from bs4 import BeautifulSoup
import json
import time
import random
from datetime import datetime

class EnergyBidSpider:
    """
    北极星储能网中标信息爬虫（仅供学习交流）
    注意：实际页面结构可能变化，需根据最新DOM调整选择器
    """

    BASE_URL = "https://chuneng.bjx.com.cn"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://chuneng.bjx.com.cn/",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.results = []

    def fetch_list(self, page=1):
        """获取中标公示列表页"""
        # TODO: 请根据实际URL结构调整
        url = f"{self.BASE_URL}/zhongbiao/list_{page}.html"
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'utf-8'
            return resp.text
        except Exception as e:
            print(f"[ERROR] 请求列表页失败: {e}")
            return None

    def parse_list(self, html):
        """解析列表页，提取详情页链接"""
        soup = BeautifulSoup(html, 'html.parser')
        items = []
        # TODO: 根据实际HTML结构修改选择器
        for tag in soup.select("ul.list-item li a"):
            title = tag.get_text(strip=True)
            href = tag.get("href", "")
            # 过滤2025年大型储能相关
            if "2025" in title and ("储能" in title or "中标" in title):
                items.append({"title": title, "url": href})
        return items

    def parse_detail(self, url):
        """解析详情页，提取中标单位、金额、参标单位"""
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # TODO: 以下为示例选择器，必须根据实际页面调整！
            content = soup.select_one("div.article-content")
            text = content.get_text("\n", strip=True) if content else ""

            record = {
                "title": soup.select_one("h1").get_text(strip=True) if soup.select_one("h1") else "",
                "url": url,
                "winner": self._extract_field(text, ["中标人", "中标单位", "中标候选人"]),
                "amount": self._extract_field(text, ["中标金额", "中标价格", "投标报价"]),
                "participants": self._extract_field(text, ["投标人", "参标单位", "候选单位"]),
                "scrape_time": datetime.now().isoformat(),
            }
            return record
        except Exception as e:
            print(f"[ERROR] 解析详情失败 {url}: {e}")
            return None

    @staticmethod
    def _extract_field(text, keywords):
        """从文本中按关键词提取字段值"""
        for kw in keywords:
            for line in text.split("\n"):
                if kw in line:
                    return line.replace(kw, "").strip(":： ").strip()
        return "未提取到"

    def run(self, max_pages=5):
        """主运行流程"""
        for page in range(1, max_pages + 1):
            print(f"[INFO] 正在爬取第 {page} 页...")
            html = self.fetch_list(page)
            if not html:
                continue
            items = self.parse_list(html)
            for item in items:
                detail = self.parse_detail(item["url"])
                if detail:
                    self.results.append(detail)
                # 礼貌延迟，避免被封
                time.sleep(random.uniform(2, 5))
            time.sleep(random.uniform(3, 6))

        # 保存结果
        with open("data/bids_2025.json", "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"[DONE] 共采集 {len(self.results)} 条记录")
        return self.results


if __name__ == "__main__":
    spider = EnergyBidSpider()
    spider.run(max_pages=3)
