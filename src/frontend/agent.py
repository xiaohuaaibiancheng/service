import os
import time
import logging
import asyncio
from typing import List, Optional
from pydantic import BaseModel, Field
import instructor
from openai import OpenAI
from serpapi import GoogleSearch
from newspaper import Article
from swarm import Swarm
from swarm import Agent
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from collections import defaultdict
import nltk
import ssl
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 导入配置
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, SERPAPI_API_KEY, OPENAI_MODEL


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 检查API密钥
if not OPENAI_API_KEY or not SERPAPI_API_KEY:
    logger.error("缺少必要的API密钥，无法继续运行。")
    exit(1)

# 初始化OpenAI客户端并应用instructor补丁
client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
instructor.patch(client=client)

# 定义基础响应模型
class ToolResult(BaseModel):
    """工具检测结果基类"""
    tool_type: str = Field(..., description="工具类型")
    result: str = Field(..., description="检测结果（可信/可疑/错误）")
    reason: str = Field(..., description="结果原因说明")
    confidence: float = Field(ge=0, le=1, description="置信度评分（0-1）")

class FactCheckReport(BaseModel):
    """事实核查最终报告"""
    basic_info: dict = Field(..., description="基本信息")
    tool_results: List[ToolResult] = Field(..., description="各工具检测结果")
    final_verdict: str = Field(..., description="最终判定结果")
    confidence: float = Field(..., ge=0, le=1, description="判定置信度")
    error_logs: List[str] = []  # 记录错误日志，便于后续分析
def analyze_title(text: str) -> ToolResult:
    """分析标题是否存在夸张或情绪化语言"""
    logger.info(f"进入analyze_title函数，输入文本：{text}")
    try:
        result = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"检查以下文本是否存在夸张、挑衅性或情绪化语言，并给出置信度评分（0-1）。直接返回JSON格式：{{'result': '可信'或'可疑'， 'reason': '原因说明'， 'confidence': 数值}}。"
            }],
            response_model=ToolResult,
            max_retries=3
        )
        logger.info(f"analyze_title模型返回结果：{result}")
        result.tool_type = "phrase_tool"
        return result
    except Exception as e:
        logger.error(f"analyze_title函数发生异常：{str(e)}")
        return ToolResult(
            tool_type="phrase_tool",
            result="错误",
            reason=str(e),
            confidence=0.0
        )

def check_grammar(text: str) -> ToolResult:
    """检查文本的语法和措辞是否正确"""
    logger.info(f"进入check_grammar函数，输入文本：{text}")
    try:
        result = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"检查以下文本是否存在语法或措辞错误，并给出置信度评分（0-1）。直接返回JSON格式：{{'result': '可信'或'可疑'， 'reason': '原因说明'， 'confidence': 数值}}。"
            }],
            response_model=ToolResult,
            max_retries=3
        )
        logger.info(f"check_grammar模型返回结果：{result}")
        result.tool_type = "language_tool"
        return result
    except Exception as e:
        logger.error(f"check_grammar函数发生异常：{str(e)}")
        return ToolResult(
            tool_type="language_tool",
            result="错误",
            reason=str(e),
            confidence=0.0
        )

def common_sense_check(text: str) -> ToolResult:
    """评估内容的合理性"""
    logger.info(f"进入common_sense_check函数，输入文本：{text}")
    try:
        result = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"评估以下内容是否符合常识，并给出置信度评分（0-1）。直接返回JSON格式：{{'result': '可信'或'可疑'， 'reason': '原因说明'， 'confidence': 数值}}。"
            }],
            response_model=ToolResult,
            max_retries=3
        )
        logger.info(f"common_sense_check模型返回结果：{result}")
        result.tool_type = "common_sense_tool"
        return result
    except Exception as e:
        logger.error(f"common_sense_check函数发生异常：{str(e)}")
        return ToolResult(
            tool_type="common_sense_tool",
            result="错误",
            reason=str(e),
            confidence=0.0
        )

def analyze_url(url: str) -> ToolResult:
    """检查URL的可信度"""
    logger.info(f"进入analyze_url函数，输入URL：{url}")
    try:
        result = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"检查以下URL的可信度，并给出置信度评分（0-1）。直接返回JSON格式：{{'result': '可信'或'可疑'， 'reason': '原因说明'， 'confidence': 数值}}。"
            }],
            response_model=ToolResult,
            max_retries=3
        )
        logger.info(f"analyze_url模型返回结果：{result}")
        result.tool_type = "url_tool"
        return result
    except Exception as e:
        logger.error(f"analyze_url函数发生异常：{str(e)}")
        return ToolResult(
            tool_type="url_tool",
            result="错误",
            reason=str(e),
            confidence=0.0
        )


def calculate_similarity(text1: str, text2: str) -> float:
    """计算两个文本的TF-IDF余弦相似度"""
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform([text1, text2])
    return cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])[0][0]

async def search_tool(keywords: List[str], title: str, text: str) -> ToolResult:
    """优化版：即使没有 organic_results，也基于 search_information 进行可信度评估"""
    logger.info(f"进入 search_tool 函数，关键词：{keywords}")
    
    try:
        if not keywords:
            return ToolResult(
                tool_type="search_tool",
                result="可疑",
                reason="缺乏关键词",
                confidence=0.0
            )

        # 组合关键词进行搜索
        query = ' '.join(keywords)
        params = {
            "engine": "bing",
            "q": query,
            "cc": "us",
            "api_key": SERPAPI_API_KEY
        }
        search = GoogleSearch(params)
        results = await asyncio.to_thread(search.get_dict)  # 让同步 API 运行在异步环境

        logger.info(f"search_tool 搜索结果：{results}")

        # 解析搜索结果
        total_results = results.get("search_information", {}).get("total_results", 0)
        snippet = results.get("search_metadata", {}).get("snippet", "")

        if total_results == 0:
            return ToolResult(
                tool_type="search_tool",
                result="可疑",
                reason="未找到相关报道",
                confidence=0.2
            )

        # 计算搜索结果与新闻标题/正文的相似度
        similarity_title = calculate_similarity(title, snippet) if title else 0
        similarity_text = calculate_similarity(text, snippet) if text else 0
        avg_similarity = (similarity_title + similarity_text) / 2

        if avg_similarity < 0.3:
            return ToolResult(
                tool_type="search_tool",
                result="可疑",
                reason="搜索结果与新闻内容相关性较低",
                confidence=0.3
            )

        # 根据相似度和搜索结果数量加权计算置信度
        confidence = min(1.0, max(0.4, (avg_similarity * 0.6 + (total_results / 1000) * 0.4)))

        return ToolResult(
            tool_type="search_tool",
            result="可信",
            reason=f"搜索结果匹配，找到 {total_results} 条记录",
            confidence=confidence
        )

    except Exception as e:
        logger.error(f"search_tool 发生异常：{str(e)}")
        return ToolResult(
            tool_type="search_tool",
            result="错误",
            reason=str(e),
            confidence=0.0
        )



def analyze_stance(text: str) -> ToolResult:
    """分析政治新闻的立场"""
    logger.info(f"进入analyze_stance函数，输入文本：{text}")
    try:
        result = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"分析以下文本是否包含政治立场偏向，并给出置信度评分（0-1）。直接返回JSON格式：{{'result': '可信'或'可疑'， 'reason': '原因说明'， 'confidence': 数值}}。"
            }],
            response_model=ToolResult,
            max_retries=3
        )
        logger.info(f"analyze_stance模型返回结果：{result}")
        result.tool_type = "stance_tool"
        return result
    except Exception as e:
        logger.error(f"analyze_stance函数发生异常：{str(e)}")
        return ToolResult(
            tool_type="stance_tool",
            result="错误",
            reason=str(e),
            confidence=0.0
        )

def analyze_content(text: str) -> ToolResult:
    """分析正文内容的一致性和可信度"""
    logger.info(f"进入analyze_content函数，输入文本：{text}")
    if not text:
        logger.warning("正文内容缺失")
        return ToolResult(
            tool_type="content_tool",
            result="可疑",
            reason="正文内容缺失",
            confidence=0.0
        )
    
    try:
        result = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"分析以下内容是否与标题一致，并给出置信度评分（0-1）。直接返回JSON格式：{{'result': '可信'或'可疑'， 'reason': '原因说明'， 'confidence': 数值}}。"
            }],
            response_model=ToolResult,
            max_retries=3
        )
        logger.info(f"analyze_content模型返回结果：{result}")
        result.tool_type = "content_tool"
        return result
    except Exception as e:
        logger.error(f"analyze_content函数发生异常：{str(e)}")
        return ToolResult(
            tool_type="content_tool",
            result="错误",
            reason=str(e),
            confidence=0.0
        )

# 定义Agent指令模板
def main_agent_instructions(context_vars):
    return """您负责协调事实核查流程，需要：
        1. 调用所有子工具收集结果
        2. 综合各工具结果生成最终报告
        3. 最终报告必须使用FactCheckReport格式
        4. 根据可疑结果数量和各工具置信度计算整体置信度
        最终判定逻辑：
        - 可疑结果≥3 → 假新闻（置信度0.2）
        - 2个可疑 → 可疑内容（置信度0.5）
        - 1个可疑 → 可能真实（置信度0.7）
        - 无不疑 → 可信内容（置信度0.9）
        如果置信度有冲突，取平均值"""

# 创建各个Agent
main_agent = Agent(
    name="main_agent",
    model=OPENAI_MODEL,
    instructions=main_agent_instructions,
    functions=[],
    response_model=FactCheckReport
)

# 初始化Swarm客户端
swarm_client = Swarm(client)

class FactChecker:
    """新闻事实核查工具类"""
    def __init__(self):
        self.swarm = swarm_client
        self.tools = {
            "phrase": analyze_title,
            "language": check_grammar,
            "common_sense": common_sense_check,
            "url": analyze_url,
            "search": search_tool,
            "stance": analyze_stance,
            "content": analyze_content
        }

    async def check_news(self, news_info: dict) -> FactCheckReport:
        """执行事实核查"""
        logger.info("开始事实核查流程")
        
        # 提取新闻内容
        article_data = await self._extract_content(news_info.get("url"))
        content={'text':news_info['text']}
        if not article_data['text']:
            article_data.update(content)
        context = {**news_info, **article_data}

        # 提取关键词
        keywords = self.extract_keywords(context.get("text", ""))

        # 使用 asyncio.gather() 并行执行多个工具
        tool_tasks = []
        error_logs = []
        
        for tool_name, tool_func in self.tools.items():
            try:
                if tool_name == "search":
                    tool_tasks.append(tool_func(keywords, context.get("title", ""), context.get("text", "")))
                else:
                    input_data = context.get("text", "") if tool_name != "url" else news_info.get("url")
                    if asyncio.iscoroutinefunction(tool_func):  # 检查是否是异步函数
                        tool_tasks.append(tool_func(input_data))
                    else:
                        tool_tasks.append(asyncio.to_thread(tool_func, input_data))  # 让同步函数在异步环境中执行
            except Exception as e:
                error_logs.append(f"{tool_name} 失败: {str(e)}")

        # 并行执行所有检测任务
        tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)

        # 处理异常结果
        final_results = []
        for result in tool_results:
            if isinstance(result, Exception):
                error_logs.append(str(result))
            else:
                final_results.append(result)

        # 生成最终报告
        return self._generate_final_report(context, final_results, error_logs)


    def extract_keywords(self, text: str, num_keywords: int = 5) -> List[str]:
        """改进关键词提取方法，使用 TF-IDF"""
        from sklearn.feature_extraction.text import TfidfVectorizer
        if not text:
            return []
        
        vectorizer = TfidfVectorizer(stop_words='english', max_features=num_keywords)
        tfidf_matrix = vectorizer.fit_transform([text])
        feature_array = vectorizer.get_feature_names_out()
        
        return list(feature_array)
    async def _extract_content(self, url: Optional[str]) -> dict:
        """提取新闻内容"""
        if not url:
            return {}
        
        try:
            article = Article(url)
            article.download()
            article.parse()
            return {
                "title": article.title,
                "text": article.text,
                "authors": article.authors,
                "publish_date": article.publish_date
            }
        except Exception as e:
            logger.error(f"内容提取失败: {str(e)}")
            return {}

    def _generate_final_report(self, context: dict, results: List[ToolResult], error_logs: List[str]) -> FactCheckReport:
        """ 生成最终事实核查报告，基于权重计算可信度 """
        logger.info("正在生成最终事实核查报告...")

        weights = {"可信": 1, "可疑": -1, "错误": -0.5}
        weighted_score = sum(weights.get(r.result, 0) * r.confidence for r in results)
        avg_confidence = sum(r.confidence for r in results if r.result != "错误") / max(len(results), 1)

        if weighted_score >= 2:
            final_verdict = "可信内容"
            confidence = max(0.9, avg_confidence)
        elif 0 <= weighted_score < 2:
            final_verdict = "可能真实"
            confidence = max(0.7, avg_confidence)
        elif -2 <= weighted_score < 0:
            final_verdict = "可疑内容"
            confidence = max(0.5, avg_confidence)
        else:
            final_verdict = "假新闻"
            confidence = max(0.2, avg_confidence)

        logger.info(f"最终判定: {final_verdict} (置信度: {confidence:.2f})")

        return FactCheckReport(
            basic_info={
                "title": context.get("title", ""),
                "url": context.get("url", ""),
                "authors": context.get("authors", []),
                "publish_date": str(context.get("publish_date", ""))
            },
            tool_results=results,
            final_verdict=final_verdict,
            confidence=confidence,
            error_logs=error_logs
        )





# 示例使用
if __name__ == "__main__":
    async def main():
        checker = FactChecker()
        news = {
            "title": "中方回应巴拿马退出一带一路协议",
            "url": "https://news.ifeng.com/c/8gmSvGxMIiV",
            "date": "2024-02-06"
        }
        
        # 执行事实核查
        report = await checker.check_news(news)
        print(report)

    asyncio.run(main())
