"""
credence_api.py - 事实核查API功能

本模块提供了事实核查和搜索结果获取的功能，模拟了原有的credence.api模块。
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
import random
from bs4 import BeautifulSoup
import hashlib

# 尝试导入配置
try:
    from src.config import SEARCH_API_KEY, SEARCH_ENGINE_ID
except ImportError:
    SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY", "AIzaSyDy2jGqcssUlgTp0Ee6QC_m5sFS9pKsgj8")
    SEARCH_ENGINE_ID = os.environ.get("SEARCH_ENGINE_ID", "")
    logging.warning("无法导入配置模块，使用环境变量")

# 尝试导入OpenAI
try:
    from src.frontend.openai_utils import get_openai_client
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("无法导入OpenAI工具，相关功能将受限")

def fact_check_text(news_text: str) -> Dict[str, Any]:
    """
    对文本进行事实核查
    
    Args:
        news_text: 需要核查的新闻文本
        
    Returns:
        Dict[str, Any]: 包含事实核查结果的字典
    """
    if not news_text:
        logging.warning("输入文本为空，无法进行事实核查")
        return create_empty_result(news_text)
    
    try:
        # 获取搜索结果
        search_results = get_search_results(news_text)
        
        if not search_results:
            logging.warning("搜索结果为空，无法进行事实核查")
            return create_empty_result(news_text)
        
        # 提取主要声明
        main_claim = extract_main_claim(news_text)
        
        # 处理搜索结果，生成证据
        evidence = []
        for result in search_results[:5]:  # 取前5个结果
            snippet = result.get('snippet', '')
            title = result.get('title', '')
            link = result.get('link', '')
            
            # 计算相关性分数
            relevance = calculate_relevance(snippet, news_text)
            
            # 判断是支持还是反对
            support_level = calculate_support_level(snippet, news_text)
            
            evidence.append({
                'source': title,
                'url': link,
                'content': snippet,
                'relevance': relevance,
                'support_level': support_level
            })
        
        # 计算综合判断
        supporting_count = sum(1 for e in evidence if e['support_level'] > 0.5)
        total_count = len(evidence)
        
        if total_count == 0:
            verdict = "未知"
            confidence = 0.5
        else:
            support_ratio = supporting_count / total_count
            if support_ratio > 0.7:
                verdict = "可信"
                confidence = 0.7 + (support_ratio - 0.7) * 0.3
            elif support_ratio < 0.3:
                verdict = "不可信"
                confidence = 0.7 + (0.3 - support_ratio) * 0.3
            else:
                verdict = "部分可信"
                confidence = 0.5 + (support_ratio - 0.5) * 0.4
        
        # 生成解释
        explanation = generate_explanation(news_text, evidence, verdict)
        
        # 整合结果
        result = {
            'verdict': verdict,
            'confidence': confidence,
            'main_claim': main_claim,
            'evidence': evidence,
            'explanation': explanation,
            'timestamp': datetime.now().isoformat()
        }
        
        # 保存结果
        save_result(result, news_text)
        
        return result
        
    except Exception as e:
        logging.error(f"事实核查过程出错: {str(e)}")
        return create_empty_result(news_text)

def get_search_results(query: str) -> List[Dict[str, Any]]:
    """
    获取搜索引擎的搜索结果
    
    Args:
        query: 搜索查询文本
        
    Returns:
        List[Dict[str, Any]]: 搜索结果列表
    """
    if not query:
        logging.warning("搜索查询为空")
        return []
    
    try:
        # 尝试使用Google自定义搜索API
        if SEARCH_API_KEY and SEARCH_ENGINE_ID:
            return google_search(query)
        else:
            # 如果没有API密钥，生成模拟的搜索结果
            return simulate_search_results(query)
    except Exception as e:
        logging.error(f"获取搜索结果出错: {str(e)}")
        return []

def google_search(query: str) -> List[Dict[str, Any]]:
    """
    使用Google自定义搜索API进行搜索
    
    Args:
        query: 搜索查询
        
    Returns:
        List[Dict[str, Any]]: 搜索结果列表
    """
    try:
        # Google自定义搜索API端点
        url = "https://www.googleapis.com/customsearch/v1"
        
        # 请求参数
        params = {
            'key': SEARCH_API_KEY,
            'cx': SEARCH_ENGINE_ID,
            'q': query,
            'num': 10
        }
        
        # 发送请求
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            results = []
            for item in items:
                results.append({
                    'title': item.get('title', ''),
                    'link': item.get('link', ''),
                    'snippet': item.get('snippet', ''),
                    'source': 'Google Search'
                })
            
            return results
        else:
            logging.error(f"Google搜索API返回错误: {response.status_code}")
            return []
    
    except Exception as e:
        logging.error(f"Google搜索出错: {str(e)}")
        return []

def simulate_search_results(query: str) -> List[Dict[str, Any]]:
    """
    生成模拟的搜索结果（当没有实际搜索API可用时）
    
    Args:
        query: 搜索查询
        
    Returns:
        List[Dict[str, Any]]: 模拟的搜索结果列表
    """
    logging.warning("使用模拟的搜索结果（非真实搜索）")
    
    # 根据查询生成一个随机种子
    query_hash = hashlib.md5(query.encode()).hexdigest()
    seed = int(query_hash[:8], 16)
    random.seed(seed)
    
    # 从查询中提取关键词
    keywords = query.split()
    if len(keywords) > 5:
        keywords = keywords[:5]
    
    # 创建一些虚拟来源
    sources = [
        "新浪新闻", "腾讯网", "网易", "搜狐", "人民日报", 
        "南方周末", "中国日报", "环球时报", "科技日报", "经济观察网",
        "纽约时报", "华盛顿邮报", "BBC中文网", "法国国际广播电台", "德国之声"
    ]
    
    # 创建一些虚拟域名
    domains = [
        "news.sina.com.cn", "news.qq.com", "news.163.com", "news.sohu.com", "people.com.cn",
        "infzm.com", "chinadaily.com.cn", "huanqiu.com", "stdaily.com", "eeo.com.cn",
        "cn.nytimes.com", "washingtonpost.com", "bbc.com/zhongwen", "rfi.fr/cn", "dw.com/zh"
    ]
    
    # 创建一些相关性分数
    relevance_scores = [0.95, 0.85, 0.78, 0.72, 0.68, 0.65, 0.62, 0.58, 0.55, 0.52]
    
    # 生成模拟结果
    results = []
    for i in range(min(10, max(5, len(query) // 5))):
        # 随机选择一个来源和域名
        source_index = random.randint(0, len(sources) - 1)
        source = sources[source_index]
        domain = domains[source_index]
        
        # 生成标题
        random_words = random.sample(keywords, min(len(keywords), 3))
        title = f"{source}：关于\"{''.join(random_words)}\"的{'调查' if i % 2 == 0 else '报道'}"
        
        # 生成链接
        path = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(8))
        link = f"https://{domain}/{path}.html"
        
        # 生成摘要
        start_phrases = ["据报道，", "近日，", "最新消息，", "专家表示，", "记者获悉，"]
        middle_phrases = ["这一情况引发了广泛关注。", "相关部门已开展调查。", "专家们对此有不同看法。", 
                        "这一事件正在持续发酵。", "公众对此反应强烈。"]
        end_phrases = ["后续发展值得关注。", "事态或将有新进展。", "更多细节有待披露。", 
                      "各方正密切关注事态发展。", "相关调查仍在进行中。"]
        
        snippet = f"{start_phrases[i % len(start_phrases)]}{query}{middle_phrases[i % len(middle_phrases)]}"\
                f"{end_phrases[i % len(end_phrases)]}"
        
        # 添加结果
        results.append({
            'title': title,
            'link': link,
            'snippet': snippet,
            'source': source,
            'relevance': relevance_scores[i % len(relevance_scores)]
        })
    
    # 恢复随机种子
    random.seed(None)
    
    return results

def extract_main_claim(text: str) -> str:
    """
    从文本中提取主要声明
    
    Args:
        text: 需要分析的文本
        
    Returns:
        str: 提取的主要声明
    """
    # 简单实现：取前100个字符作为主要声明
    if not text:
        return ""
    
    # 去除多余空格
    text = ' '.join(text.split())
    
    # 截取前面的文本
    if len(text) <= 100:
        return text
    else:
        # 找到第一个句号，问号或感叹号
        for i in range(80, min(150, len(text))):
            if text[i] in ['.', '。', '!', '！', '?', '？']:
                return text[:i+1]
        
        # 如果找不到合适的断句点，返回前100个字符
        return text[:100]

def calculate_relevance(snippet: str, query: str) -> float:
    """
    计算片段与查询的相关性
    
    Args:
        snippet: 文本片段
        query: 查询文本
        
    Returns:
        float: 相关性分数，范围0-1
    """
    if not snippet or not query:
        return 0.0
    
    # 将文本转换为词集合
    snippet_words = set(snippet.lower().split())
    query_words = set(query.lower().split())
    
    # 计算交集大小
    common_words = snippet_words.intersection(query_words)
    
    # 计算Jaccard相似度
    if not snippet_words or not query_words:
        return 0.0
    
    similarity = len(common_words) / (len(snippet_words) + len(query_words) - len(common_words))
    
    # 调整分数使其更有区分度
    adjusted_score = 0.5 + similarity * 0.5
    
    return min(1.0, max(0.0, adjusted_score))

def calculate_support_level(snippet: str, claim: str) -> float:
    """
    计算片段对声明的支持程度
    
    Args:
        snippet: 文本片段
        claim: 声明文本
        
    Returns:
        float: 支持程度，范围0-1，0表示完全反对，1表示完全支持
    """
    # 一个简单的启发式实现
    # 在实际项目中，这里应该使用更复杂的NLP技术
    
    # 计算相关性
    relevance = calculate_relevance(snippet, claim)
    
    # 创建一个简单的支持/反对词表
    support_words = ['证实', '确认', '证明', '支持', '表明', '显示', '事实是', '的确', '确实', '正确']
    oppose_words = ['否认', '反驳', '质疑', '不实', '虚假', '错误', '谣言', '不正确', '不真实', '假的']
    
    # 计算支持和反对词的出现次数
    support_count = sum(1 for word in support_words if word in snippet)
    oppose_count = sum(1 for word in oppose_words if word in snippet)
    
    # 计算支持程度
    if support_count == 0 and oppose_count == 0:
        # 没有明确的支持或反对词，返回中性值
        return 0.5
    elif oppose_count == 0:
        # 只有支持词，没有反对词
        return min(0.8, 0.5 + 0.1 * support_count)
    elif support_count == 0:
        # 只有反对词，没有支持词
        return max(0.2, 0.5 - 0.1 * oppose_count)
    else:
        # 同时有支持词和反对词
        ratio = support_count / (support_count + oppose_count)
        return 0.3 + ratio * 0.4  # 范围从0.3到0.7
    
def generate_explanation(news_text: str, evidence: List[Dict[str, Any]], verdict: str) -> str:
    """
    根据证据和结论生成解释
    
    Args:
        news_text: 新闻文本
        evidence: 证据列表
        verdict: 结论
        
    Returns:
        str: 生成的解释文本
    """
    # 提取主要声明
    main_claim = extract_main_claim(news_text)
    
    # 统计支持和反对的证据
    supporting = [e for e in evidence if e.get('support_level', 0) > 0.5]
    opposing = [e for e in evidence if e.get('support_level', 0) <= 0.5]
    
    # 生成解释
    if verdict == "可信":
        explanation = f"经过分析，该声明\"{main_claim}\"得到了多个来源的支持。"
        if supporting:
            top_support = max(supporting, key=lambda x: x.get('relevance', 0))
            explanation += f"其中\"{top_support.get('source', '')}\"的报道直接佐证了该说法。"
    elif verdict == "不可信":
        explanation = f"经过分析，该声明\"{main_claim}\"缺乏事实依据。"
        if opposing:
            top_oppose = max(opposing, key=lambda x: x.get('relevance', 0))
            explanation += f"多个来源包括\"{top_oppose.get('source', '')}\"对此表示质疑。"
    else:  # 部分可信
        explanation = f"经过分析，该声明\"{main_claim}\"部分内容可信，但也包含一些有争议的信息。"
        if supporting and opposing:
            explanation += "不同来源对此有不同的看法和解读。"
    
    return explanation

def create_empty_result(news_text: str) -> Dict[str, Any]:
    """
    创建空的结果模板
    
    Args:
        news_text: 新闻文本
        
    Returns:
        Dict[str, Any]: 空的结果字典
    """
    main_claim = extract_main_claim(news_text) if news_text else ""
    
    return {
        'verdict': '未知',
        'confidence': 0.5,
        'main_claim': main_claim,
        'evidence': [],
        'explanation': '无法获取足够的信息进行事实核查',
        'timestamp': datetime.now().isoformat()
    }

def save_result(result: Dict[str, Any], news_text: str) -> None:
    """
    保存事实核查结果到文件
    
    Args:
        result: 事实核查结果
        news_text: 新闻文本
    """
    try:
        # 创建唯一的文件名
        text_hash = hashlib.md5(news_text.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"fact_check_{timestamp}_{text_hash}.json"
        
        # 确保目录存在
        results_dir = os.path.join(os.path.dirname(__file__), '../static/frontend', 'search_results')
        os.makedirs(results_dir, exist_ok=True)
        
        # 保存文件
        file_path = os.path.join(results_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        logging.info(f"事实核查结果已保存到: {file_path}")
    except Exception as e:
        logging.error(f"保存事实核查结果失败: {str(e)}") 