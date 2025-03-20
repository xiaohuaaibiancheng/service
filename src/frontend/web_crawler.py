import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import random
import json
import urllib.parse
from newspaper import Article
import re

class MultiPlatformNewsCrawler:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive'
        }
        
    def _random_delay(self):
        """添加较短的随机延迟"""
        time.sleep(random.uniform(0.1, 0.5))

    def search_by_platform(self, keyword, platform):
        """根据指定平台搜索新闻"""
        try:
            print(f"开始搜索平台 {platform} 的新闻，关键词: {keyword}")  # 添加调试日志
            
            if platform == "sina" or platform == "新浪新闻":
                return self.search_sina(keyword)
            elif platform == "sogou" or platform == "搜狗新闻":
                return self.search_sogou(keyword)
            elif platform == "baidu" or platform == "百度新闻":
                return self.search_baidu(keyword)
            elif platform == "cctv" or platform == "央视网":
                return self.search_cctv(keyword)
            elif platform == "chinanews" or platform == "中新网":
                return self.search_chinanews(keyword)
        except Exception as e:
            print(f"Error in search_by_platform for {platform}: {str(e)}")
            return []

    def search_sogou(self, keyword):
        """搜索搜狗新闻"""
        try:
            encoded_keyword = urllib.parse.quote(keyword)
            url = f'https://www.sogou.com/web?query={encoded_keyword}&ie=utf8&_ast=1401342476&_asf=null&w=01019900&p=40040100&dp=1&cid=&s_from=result_up'
            
            headers = self.headers.copy()
            headers.update({
                'Referer': 'https://www.sogou.com',
                'Host': 'www.sogou.com',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            })
            
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            news_list = []
            for item in soup.select('.vrwrap'):
                try:
                    title_elem = item.select_one('h3 a')
                    summary_elem = item.select_one('.text-layout')
                    info_elem = item.select_one('.news-info')
                    
                    if title_elem:
                        url = title_elem.get('href', '')
                        if url.startswith('//'):
                            url = 'https:' + url
                        elif url.startswith('/'):
                            url = 'https://www.sogou.com' + url
                            
                        news = {
                            'title': title_elem.text.strip(),
                            'url': url,
                            'summary': summary_elem.text.strip() if summary_elem else '暂无摘要',
                            'publish_time': info_elem.text.strip() if info_elem else '未知时间',
                            'source': '搜狗新闻',
                            'credibility': random.randint(70, 100)
                        }
                        news_list.append(news)
                        print(f"找到搜狗新闻: {news['title']}")
                except Exception as e:
                    print(f"解析搜狗新闻项时出错: {str(e)}")
                    continue
                    
            return news_list[:10]
        except Exception as e:
            print(f"搜狗新闻搜索出错: {str(e)}")
            return []

    # def search_sina(self, keyword):
    #     """搜索新浪新闻"""
    #     try:
    #         encoded_keyword = urllib.parse.quote(keyword)
    #         # 使用新浪新闻的搜索接口
    #         url = f'https://search.sina.com.cn/news?q={encoded_keyword}&c=news&from=channel&ie=utf-8'
            
    #         headers = self.headers.copy()
    #         headers.update({
    #             'Referer': 'https://search.sina.com.cn/',
    #             'Host': 'search.sina.com.cn',
    #             'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    #             'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    #             'Connection': 'keep-alive',
    #             'Cache-Control': 'max-age=0',
    #             'Cookie': 'SINAGLOBAL=' + ''.join(random.choices('0123456789abcdef', k=32))
    #         })
            
    #         response = requests.get(url, headers=headers, timeout=10)
    #         response.encoding = 'utf-8'
    #         soup = BeautifulSoup(response.text, 'html.parser')
            
    #         news_list = []
            
    #         # 使用新的选择器模式
    #         items = soup.select('.box-result') or soup.select('.result') or soup.select('div[class*="result"]')
            
    #         for item in items:
    #             try:
    #                 # 标题和链接
    #                 title_elem = item.select_one('h2 a, .tit a, a')
    #                 if not title_elem:
    #                     continue
                        
    #                 title = title_elem.get_text(strip=True)
    #                 url = title_elem.get('href', '')
    #                 if not url.startswith('http'):
    #                     url = 'https:' + url if url.startswith('//') else 'https://news.sina.com.cn' + url
                    
    #                 # 摘要
    #                 summary_elem = item.select_one('.content, .summary, p')
    #                 summary = summary_elem.get_text(strip=True) if summary_elem else '暂无摘要'
                    
    #                 # 时间和来源
    #                 time_source = item.select_one('.fgray_time, .time-source, .source-time')
    #                 publish_time = '未知时间'
    #                 source = '新浪新闻'
                    
    #                 if time_source:
    #                     text = time_source.get_text(strip=True)
    #                     # 提取时间
    #                     time_match = re.search(r'(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?\s*\d{1,2}:\d{1,2})', text)
    #                     if time_match:
    #                         publish_time = time_match.group(1)
                        
    #                     # 提取来源
    #                     source_match = re.search(r'来源[：:]\s*([^\s]+)', text)
    #                     if source_match:
    #                         source = source_match.group(1)
                    
    #                 news = {
    #                     'title': title,
    #                     'url': url,
    #                     'summary': summary,
    #                     'publish_time': publish_time,
    #                     'source': source,
    #                     'credibility': random.randint(70, 95)
    #                 }
                    
    #                 news_list.append(news)
    #                 print(f"找到新浪新闻: {title}")
                    
    #             except Exception as e:
    #                 print(f"解析新浪新闻项时出错: {str(e)}")
    #                 continue
            
    #         # 如果第一次尝试失败，使用备用URL
    #         if not news_list:
    #             backup_url = f'https://search.sina.com.cn/?q={encoded_keyword}&range=all&c=news&sort=time'
    #             response = requests.get(backup_url, headers=headers, timeout=10)
    #             response.encoding = 'utf-8'
    #             soup = BeautifulSoup(response.text, 'html.parser')
                
    #             items = soup.select('.new-peo') or soup.select('.box-result') or soup.select('div[class*="result"]')
                
    #             for item in items:
    #                 try:
    #                     title_elem = item.select_one('h2 a, .tit a, a')
    #                     if not title_elem:
    #                         continue
                            
    #                     title = title_elem.get_text(strip=True)
    #                     url = title_elem.get('href', '')
    #                     if not url.startswith('http'):
    #                         url = 'https:' + url if url.startswith('//') else 'https://news.sina.com.cn' + url
                        
    #                     summary_elem = item.select_one('.content, .summary, p')
    #                     summary = summary_elem.get_text(strip=True) if summary_elem else '暂无摘要'
                        
    #                     news = {
    #                         'title': title,
    #                         'url': url,
    #                         'summary': summary,
    #                         'publish_time': '未知时间',
    #                         'source': '新浪新闻',
    #                         'credibility': random.randint(70, 95)
    #                     }
                        
    #                     news_list.append(news)
    #                     print(f"找到新浪新闻: {title}")
                        
    #                 except Exception as e:
    #                     print(f"解析新浪新闻项时出错: {str(e)}")
    #                     continue
            
    #         if not news_list:
    #             print("未找到任何新浪新闻")
    #         else:
    #             print(f"成功提取 {len(news_list)} 条新浪新闻")
            
    #         return news_list[:10]  # 限制返回前10条结果
            
    #     except Exception as e:
    #         print(f"新浪新闻搜索出错: {str(e)}")
    #         return []

    def search_baidu(self, keyword):
        """搜索百度新闻"""
        try:
            encoded_keyword = urllib.parse.quote(keyword)
            url = f'https://www.baidu.com/s?rtt=1&bsst=1&cl=2&tn=news&word={encoded_keyword}'
            
            headers = self.headers.copy()
            headers.update({
                'Referer': 'https://www.baidu.com',
                'Host': 'www.baidu.com',
                'Cookie': 'BAIDUID=' + ''.join(random.choices('0123456789ABCDEF', k=32))
            })
            
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            news_list = []
            for item in soup.select('.result'):
                try:
                    title_elem = item.select_one('h3 a')
                    summary_elem = item.select_one('.c-summary')
                    source_time_elem = item.select_one('.c-author')
                    
                    if title_elem:
                        news = {
                            'title': title_elem.text.strip(),
                            'url': title_elem['href'],
                            'summary': summary_elem.text.strip() if summary_elem else '暂无摘要',
                            'publish_time': source_time_elem.text.strip() if source_time_elem else '未知时间',
                            'source': '百度新闻',
                            'credibility': random.randint(70, 100)
                        }
                        news_list.append(news)
                        print(f"找到百度新闻: {news['title']}")
                except Exception as e:
                    print(f"解析百度新闻项时出错: {str(e)}")
                    continue
                    
            # 如果上面的选择器没有找到结果，尝试备用选择器
            if not news_list:
                for item in soup.select('.c-container'):
                    try:
                        title_elem = item.select_one('h3 a')
                        summary_elem = item.select_one('.c-summary')
                        source_time_elem = item.select_one('.c-author')
                        
                        if title_elem:
                            news = {
                                'title': title_elem.text.strip(),
                                'url': title_elem['href'],
                                'summary': summary_elem.text.strip() if summary_elem else '暂无摘要',
                                'publish_time': source_time_elem.text.strip() if source_time_elem else '未知时间',
                                'source': '百度新闻',
                                'credibility': random.randint(70, 100)
                            }
                            news_list.append(news)
                            print(f"找到百度新闻: {news['title']}")
                    except Exception as e:
                        print(f"解析百度新闻项时出错: {str(e)}")
                        continue
                        
            return news_list[:10]
        except Exception as e:
            print(f"百度新闻搜索出错: {str(e)}")
            return [] 

    def search_cctv(self, keyword):
        """搜索央视网新闻"""
        try:
            base_url = "https://search.cctv.com/search.php"
            
            params = {
                "qtext": keyword,
                "sort": "date",
                "type": "web",
                "page": 1,
            }
            
            headers = self.headers.copy()
            headers.update({
                'Referer': 'https://search.cctv.com',
                'Host': 'search.cctv.com'
            })
            
            response = requests.get(base_url, params=params, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                print("无法获取央视网页面内容。")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.find_all('li', class_="image")
            
            news_list = []
            for item in items[:10]:  # 限制为前10条结果
                try:
                    # 提取标题和中转链接
                    title_tag = item.find('a', id=lambda x: x and x.startswith("web_content_"))
                    if not title_tag:
                        continue
                        
                    title = title_tag.get_text(strip=True)
                    encoded_link = title_tag['href']
                    
                    # 解码出实际内容链接
                    match = re.search(r'targetpage=([^&]+)', encoded_link)
                    if not match:
                        continue
                        
                    url = urllib.parse.unquote(match.group(1))
                    
                    # 提取摘要、来源、时间
                    summary_tag = item.find('p', class_="bre")
                    summary = summary_tag.get_text(strip=True) if summary_tag else "暂无摘要"

                    source_tag = item.find('span', class_="src")
                    source = source_tag.get_text(strip=True) if source_tag else "央视网"
                    
                    timestamp_tag = item.find('span', class_="tim")
                    publish_time = timestamp_tag.get_text(strip=True) if timestamp_tag else "未知时间"
                    
                    news = {
                        'title': title,
                        'url': url,
                        'summary': summary,
                        'publish_time': publish_time,
                        'source': source or '央视网',
                        'credibility': random.randint(80, 100)  # 央视网的可信度设置得更高一些
                    }
                    
                    news_list.append(news)
                    print(f"找到央视网新闻: {title}")
                    
                except Exception as e:
                    print(f"解析央视网新闻项时出错: {str(e)}")
                    continue
            
            if not news_list:
                print("未找到任何央视网新闻")
            else:
                print(f"成功提取 {len(news_list)} 条央视网新闻")
            
            return news_list
            
        except Exception as e:
            print(f"央视网搜索出错: {str(e)}")
            return []

    def search_chinanews(self, keyword):
        """搜索中新网新闻"""
        try:
            url = f"https://sou.chinanews.com.cn/search.do?q={urllib.parse.quote(keyword)}"
            
            headers = self.headers.copy()
            headers.update({
                'Referer': 'https://sou.chinanews.com.cn',
                'Host': 'sou.chinanews.com.cn'
            })
            
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                print("无法获取中新网页面内容。")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            script_text = soup.find("script", text=re.compile("var docArr"))
            
            news_list = []
            if script_text:
                try:
                    # 提取JSON数据
                    docArr_json_text = re.search(r"var docArr = (\[.*?\]);", script_text.string).group(1)
                    docArr_data = json.loads(docArr_json_text)
                    
                    for item in docArr_data[:10]:  # 限制为前10条结果
                        title = item.get("title", "")
                        if isinstance(title, str):
                            title = title.replace("<em>", "").replace("</em>", "")
                        elif isinstance(title, list):
                            title = " ".join(str(t) for t in title) if title else ""
                            
                        url = item.get("url", "")
                        
                        content = item.get("content_without_tag", "")
                        if isinstance(content, str):
                            content = content.replace("<em>", "").replace("</em>", "")
                        elif isinstance(content, list):
                            content = " ".join(str(c) for c in content) if content else ""
                            
                        pubtime = item.get("pubtime", "未知时间")
                        
                        news = {
                            'title': title,
                            'url': url,
                            'summary': content,
                            'publish_time': pubtime,
                            'source': '中新网',
                            'credibility': random.randint(75, 95)  # 中新网的可信度设置在75-95之间
                        }
                        
                        news_list.append(news)
                        print(f"找到中新网新闻: {title}")
                        
                except Exception as e:
                    print(f"解析中新网JSON数据时出错: {str(e)}")
            
            if not news_list:
                print("未找到任何中新网新闻")
            else:
                print(f"成功提取 {len(news_list)} 条中新网新闻")
            
            return news_list
            
        except Exception as e:
            print(f"中新网搜索出错: {str(e)}")
            return [] 

    def search_all_platforms(self, keyword):
        """搜索所有平台的新闻"""
        print(f"开始搜索所有平台，关键词: {keyword}")  # 调试日志
        all_news = []
        
        # 更新平台列表，添加央视网和新中网
        platforms = ['sina', 'sogou', 'baidu', 'cctv', 'chinanews']
        for platform in platforms:
            try:
                news_list = self.search_by_platform(keyword, platform)
                print(f"{platform} 找到 {len(news_list)} 条新闻")  # 调试日志
                all_news.extend(news_list)
                self._random_delay()
            except Exception as e:
                print(f"Error searching {platform}: {str(e)}")
                continue
        
        # 对结果进行去重和排序
        unique_news = []
        seen_titles = set()
        
        for news in all_news:
            if news['title'] not in seen_titles:
                seen_titles.add(news['title'])
                unique_news.append(news)
                
        # 按发布时间排序
        unique_news.sort(key=lambda x: x['publish_time'], reverse=True)
        print(f"总共找到 {len(unique_news)} 条不重复新闻")  # 调试日志
        
        # 生成统计数据
        stats = {
            'sources': {},  # 来源分布
            'timeline': []  # 传播时间线
        }
        
        # 统计来源分布
        for news in unique_news:
            source = news['source']
            stats['sources'][source] = stats['sources'].get(source, 0) + 1
        
        # 生成传播时间线数据
        timeline_data = {}
        for news in unique_news:
            try:
                # 尝试解析时间
                time_str = news['publish_time']
                if '分钟前' in time_str:
                    minutes = int(time_str.replace('分钟前', ''))
                    time_point = datetime.now() - timedelta(minutes=minutes)
                elif '小时前' in time_str:
                    hours = int(time_str.replace('小时前', ''))
                    time_point = datetime.now() - timedelta(hours=hours)
                else:
                    # 如果是具体时间，尝试解析
                    time_point = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
                
                date_str = time_point.strftime('%Y-%m-%d %H:00')
                timeline_data[date_str] = timeline_data.get(date_str, 0) + 1
            except:
                continue
        
        # 将时间线数据转换为列表格式
        stats['timeline'] = [
            {'time': k, 'count': v}
            for k, v in sorted(timeline_data.items())
        ]
        
        return {
            'news': unique_news,
            'stats': stats
        }