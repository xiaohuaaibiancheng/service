import os
import json
import random
from datetime import datetime, timedelta
import uuid
from typing import Dict, List, Optional, Any, Union
import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# 导入配置
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_TEMPERATURE

from src.frontend.models import (
    NewsAnalysisResult, Credibility, CredibilityDimensionScores,
    VerificationInfo, Propagation, TimelineEvent, UserProfile, Relations
)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_llm_client(api_key=None, base_url=None):
    """获取LLM客户端"""
    # 优先使用传入的API密钥，其次使用配置中的密钥
    api_key = api_key or OPENAI_API_KEY
    base_url = base_url or OPENAI_BASE_URL
    
    if not api_key:
        logger.warning("未提供OpenAI API密钥，将使用模拟数据")
        return None
    
    try:
        llm = ChatOpenAI(
            model_name=OPENAI_MODEL,
            temperature=OPENAI_TEMPERATURE,
            openai_api_key=api_key,
            openai_api_base=base_url
        )
        return llm
    except Exception as e:
        logger.error(f"初始化LLM客户端失败: {str(e)}")
        return None

def analyze_with_llm(title: str, content: str, image_url: str = "", api_key: str = None, base_url: str = None) -> Dict:
    """使用大模型分析内容并生成结构化数据"""
    llm = get_llm_client(api_key, base_url)
    
    if not llm:
        # 如果无法获取LLM客户端，返回模拟数据
        return generate_mock_analysis(title, content, image_url)
    
    # 构建提示模板
    template = """
    你是一个专业的新闻分析AI助手。请分析以下新闻内容，并生成详细的结构化分析结果。
    
    新闻标题: {title}
    新闻内容: {content}
    图片URL: {image_url}
    
    请从以下几个方面进行分析：
    1. 内容可信度：评估内容的真实性、一致性和可靠性
    2. 来源可信度：评估信息来源的权威性和可靠性
    3. 逻辑可信度：评估内容的逻辑性和连贯性
    4. 传播特征：评估内容的传播方式和特点
    5. AI生成可能性：评估内容是否可能由AI生成
    
    请生成一个JSON格式的分析结果，必须严格包含以下字段，格式必须完全一致：
    ```json
    {{
        "news_id": "news_plf01A00002", // 格式为"news_plf"后跟两位数字+"A"+五位数字
        "publish_time": "2023/2/1", // 格式为"YYYY/M/D"
        "platform": "互联网平台", // 平台名称
        "check_time": "2023/2/2", // 当前日期，格式为"YYYY/M/D"
        "label": "谣言", // "真实"、"谣言"或"未确认"
        "url": "", // URL，可为空
        "title": "新闻标题",
        "content": "新闻内容摘要...",
        "pic_url": "", // 图片URL，可为空
        "hashtag": "", // 分析内容的类别
        "summary": "", // 分析内容摘要
        "credibility": {{
            "score": 0.22, // 总体可信度评分，0-1之间
            "dimension_scores": {{
                "source": 0.02, // 来源可信度评分，0-1之间
                "content": 0.4, // 内容可信度评分，0-1之间
                "logic": 0.0, // 逻辑可信度评分，0-1之间
                "propagation": 0.44, // 传播可信度评分，0-1之间
                "AI": 0.0, // AI生成内容评分，0-1之间
                "content1": "", // 内容分析1，可为空
                "content2": "" // 内容分析2，可为空
            }},
            "verification": {{
                "crowdsource_progress": 7, // 众包验证进度，整数
                "verified": true // 是否已验证，布尔值
            }}
        }},
        "propagation": {{
            "timeline": [
                {{
                    "timestamp": "2023-01-31T14:05:00.000000", // ISO格式时间戳
                    "platform": "微信", // 传播平台
                    "shares": 20, // 分享数量，整数
                    "geo_distribution": {{ // 地理分布，键为地区名，值为整数
                        "陕西": 4,
                        "海南": 4,
                        "山西": 7
                    }}
                }}
            ],
            "user_profile": {{
                "age_dist": {{ // 年龄分布，键为年龄段，值为整数
                    "18-25": 72,
                    "26-35": 6,
                    "36-50": 23
                }},
                "device_ratio": {{ // 设备比例，键为设备类型，值为整数
                    "Mobile": 83,
                    "PC": 17
                }}
            }}
        }},
        "relations": {{
            "related_rumors": [ // 相关谣言ID数组
                "news_plf05A00738",
                "news_plf09A00037"
            ],
            "knowledge_nodes": [ // 知识节点数组
                "关键词1",
                "关键词2",
                "关键词3"
            ]
        }},
        "iscredit": false, // 是否可信，布尔值
        "location": "重庆" // 地点
        "conclusion": "总结整个新闻是否可信，给出综合结论"//总结整个新闻是否可信，给出综合结论
    }}
    ```
    
    请确保生成的JSON格式正确，可以被解析，并且字段名称和结构与上面的示例完全一致。
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    
    # 创建输出解析器
    parser = JsonOutputParser()
    
    # 创建链
    chain = prompt | llm | parser
    
    try:
        # 执行链
        result = chain.invoke({
            "title": title,
            "content": content,
            "image_url": image_url
        })
        
        # 确保结果符合我们的模型
        validated_result = NewsAnalysisResult(**result).model_dump()
        print('validated_result',validated_result)
        return validated_result
    except Exception as e:
        logger.error(f"LLM分析失败: {str(e)}")
        # 如果分析失败，返回模拟数据
        return generate_mock_analysis(title, content, image_url)

def generate_mock_analysis(title: str, content: str, image_url: str = "") -> Dict:
    """生成模拟的分析数据"""
    # 创建基本的可信度评分
    source_score = round(random.uniform(0.1, 0.9), 2)
    content_score = round(random.uniform(0.1, 0.9), 2)
    logic_score = round(random.uniform(0.1, 0.9), 2)
    propagation_score = round(random.uniform(0.1, 0.9), 2)
    ai_score = round(random.uniform(0.1, 0.9), 2)
    
    # 计算总体可信度评分
    overall_score = round((source_score + content_score + logic_score + propagation_score) / 4, 2)
    
    # 确定标签
    if overall_score > 0.7:
        label = "事实"
        iscredit = True
    elif overall_score < 0.3:
        label = "谣言"
        iscredit = False
    else:
        label = "未确认"
        iscredit = False
    
    # 生成新闻ID
    news_id = f"news_plf{random.randint(1, 10):02d}A{random.randint(1, 9999):05d}"
    
    # 当前日期，格式为YYYY/M/D
    current_date = datetime.now().strftime("%Y/%m/%d")
    
    # 创建时间线事件
    timeline_events = [
        TimelineEvent(
            timestamp=datetime.now().isoformat(),
            platform="微信",
            shares=random.randint(10, 100),
            geo_distribution={
                "北京": random.randint(1, 10),
                "上海": random.randint(1, 10),
                "广州": random.randint(1, 10)
            }
        ).model_dump(),
        TimelineEvent(
            timestamp=(datetime.now() - timedelta(days=1)).isoformat(),
            platform="微博",
            shares=random.randint(10, 100),
            geo_distribution={
                "成都": random.randint(1, 10),
                "重庆": random.randint(1, 10)
            }
        ).model_dump()
    ]
    
    # 创建用户画像
    user_profile = UserProfile(
        age_dist={
            "18-25": random.randint(10, 80),
            "26-35": random.randint(10, 50),
            "36-50": random.randint(10, 50)
        },
        device_ratio={
            "Mobile": random.randint(60, 90),
            "PC": random.randint(10, 40)
        }
    ).model_dump()
    
    # 提取关键词作为知识节点
    words = content[:100].split()
    knowledge_nodes = [word for word in words if len(word) > 1][:5] if words else ["关键词1", "关键词2", "关键词3"]
    
    # 创建完整的分析结果
    result = NewsAnalysisResult(
        news_id=news_id,
        publish_time=current_date,
        platform="互联网平台",
        check_time=current_date,
        label=label,
        url="",
        title=title,
        content=content[:200] + "..." if len(content) > 200 else content,
        pic_url=image_url,
        hashtag="",
        summary=content[:100] + "..." if len(content) > 100 else content,
        credibility=Credibility(
            score=overall_score,
            dimension_scores=CredibilityDimensionScores(
                source=source_score,
                content=content_score,
                logic=logic_score,
                propagation=propagation_score,
                AI=ai_score,
                content1="",
                content2=""
            ),
            verification=VerificationInfo(
                crowdsource_progress=random.randint(1, 10),
                verified=bool(random.getrandbits(1))
            )
        ),
        propagation=Propagation(
            timeline=timeline_events,
            user_profile=user_profile
        ),
        relations=Relations(
            related_rumors=[f"news_plf{random.randint(1, 10):02d}A{random.randint(1, 9999):05d}" for _ in range(2)],
            knowledge_nodes=knowledge_nodes
        ),
        iscredit=iscredit,
        location=random.choice(["北京", "上海", "广州", "深圳", "成都", "重庆"])
    )
    
    return result.model_dump() 