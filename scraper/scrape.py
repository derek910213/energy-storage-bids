def parse_list(page_url):
    """
    解析列表页，提取所有储能相关招标条目的链接和标题
    """
    # 1. 升级请求头，全面伪装成真实浏览器
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://news.bjx.com.cn/",
        "Connection": "keep-alive",
    }
    
    try:
        resp = requests.get(page_url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        
        # 2. 【核心调试】把服务器返回的真实HTML打印出来，看看是不是被拦截了
        print(f"[DEBUG] 列表页状态码: {resp.status_code}")
        print(f"[DEBUG] 列表页HTML前500个字符:\n{resp.text[:500]}")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = []
        
        # 3. 寻找包含链接的标签（北极星通常使用特定的class，这里用通用方式兼容）
        # 优先找带有 title 属性的 a 标签
        a_tags = soup.find_all('a', href=True, title=True)
        
        # 如果上面找不到，尝试找列表容器下的 a 标签
        if not a_tags:
            list_container = soup.find('ul', class_=re.compile(r'list|news', re.I))
            if list_container:
                a_tags = list_container.find_all('a', href=True)

        for a_tag in a_tags:
            title = a_tag.get('title', a_tag.get_text(strip=True))
            href = a_tag['href']
            
            # 只保留包含"储能"关键词的条目
            if '储能' in title:
                if not href.startswith('http'):
                    href = 'https://news.bjx.com.cn' + href
                items.append({'title': title, 'url': href})
                
        return items
    except Exception as e:
        print(f"[ERROR] 列表页解析失败: {e}")
        return []
