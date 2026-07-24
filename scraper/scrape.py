def parse_list(page_url):base_url = "https://ggzyjy.shandong.gov.cn/search.jspx?q=%25E4%25B8%25AD%25E6%25A0%2587%25E5%2585%25AC%25E5%2591%258A"
    """
    解析山东省公共资源交易网的搜索结果页
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    }
    
    try:
        resp = requests.get(page_url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        items = []
        # 核心：定位到包含所有搜索结果的列表
        # 根据网页结构，每个结果项都是一个 <li> 标签
        for li_tag in soup.find_all('li'):
            # 在每个 <li> 标签里找标题链接 <a>
            a_tag = li_tag.find('a')
            if a_tag and a_tag.get('title'): # 确保找到了a标签且有title属性
                title = a_tag['title']
                href = a_tag['href']
                
                # 确保链接是完整的
                if not href.startswith('http'):
                    href = 'https://ggzyjy.shandong.gov.cn' + href
                
                items.append({'title': title, 'url': href})
                print(f"[+] 发现项目: {title}")
                
        print(f"[INFO] 本页共发现 {len(items)} 条记录")
        return items
    except Exception as e:
        print(f"[ERROR] 列表页解析失败: {e}")
        return []
