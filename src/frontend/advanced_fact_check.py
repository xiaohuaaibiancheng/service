#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
高级事实核查服务：供Flask路由调用的接口，整合了多源证据检索与AI分析功能

基于 fact_check_system.py 的核心功能，提供了供Web API调用的接口
"""

import os
import json
import sys
import logging
import time
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime

# 添加项目根目录到路径，确保能导入additional目录下的模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from additional.AiSearch import PerplexicaSearch
from additional.fact_check_system import (
    Evidence, Contradiction, FactCheckResult, FactCheckSystem, EnhancedEvidenceRetriever
)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AdvancedFactChecker:
    """高级事实核查器：封装了FactCheckSystem，提供易于集成到Web API的接口"""

    def __init__(self,
                searx_host: str = "http://localhost:4000",
                perplexica_port: int = 3001,
                proxy_port: Optional[int] = None,
                perplexica_timeout: int = 120,
                use_openai: bool = True,
                save_results: bool = True):
        """
        初始化高级事实核查器

        Args:
            searx_host: SearxNG服务器地址
            perplexica_port: Perplexica API端口号
            proxy_port: 代理端口号
            perplexica_timeout: Perplexica请求超时时间（秒）
            use_openai: 是否使用OpenAI
            save_results: 是否保存搜索结果
        """
        # 获取API密钥和基础URL
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.openai_base_url = os.environ.get("OPENAI_API_BASE_URL", "https://api.chatanywhere.tech")

        # 默认聊天模型配置
        self.default_chat_model = {
            "provider": "custom_openai",
            "model": "gpt-4o-mini",
            "customOpenAIKey": self.openai_api_key,
            "customOpenAIBaseURL": self.openai_base_url
        }

        # 默认嵌入模型配置
        self.default_embedding_model = {
            "provider": "openai",
            "model": "text-embedding-3-small"
        }

        # 初始化事实核查系统
        self.system = FactCheckSystem(
            use_openai=use_openai,
            searx_host=searx_host,
            perplexica_port=perplexica_port,
            proxy_port=proxy_port,
            save_results=save_results,
            chat_model=self.default_chat_model,
            embedding_model=self.default_embedding_model,
            openai_api_key=self.openai_api_key,
            openai_base_url=self.openai_base_url,
            perplexica_timeout=perplexica_timeout
        )

        logger.info(f"高级事实核查器初始化完成，代理端口: {proxy_port}, 超时: {perplexica_timeout}秒")

    def check_fact(self,
                  news_text: str,
                  use_images: bool = False,
                  custom_chat_model: Optional[Dict[str, Any]] = None,
                  custom_embedding_model: Optional[Dict[str, Any]] = None,
                  timeout: Optional[int] = None,
                  save_results: Optional[bool] = None) -> Dict[str, Any]:
        """
        执行事实核查并返回字典格式的结果

        Args:
            news_text: 新闻文本
            use_images: 是否包含图片证据
            custom_chat_model: 自定义聊天模型配置
            custom_embedding_model: 自定义嵌入模型配置
            timeout: 超时时间（秒）
            save_results: 是否保存搜索结果到文件（如不指定则使用初始化时的设置）

        Returns:
            字典格式的事实核查结果
        """
        start_time = time.time()

        # 如果设置了超时，更新Perplexica客户端的超时配置
        if timeout and self.system.retriever.perplexica_retriever.available:
            self.system.retriever.perplexica_retriever.client.set_timeout(timeout)
            logger.info(f"设置Perplexica超时时间为 {timeout}秒")

        # 执行事实核查
        try:
            # 如果未指定save_results，则使用系统默认值
            save_source_results = save_results if save_results is not None else self.system.save_results

            result = self.system.check_fact(
                news_text=news_text,
                use_images=use_images,
                custom_chat_model=custom_chat_model,
                custom_embedding_model=custom_embedding_model,
                save_source_results=save_source_results
            )

            # 计算处理时间
            processing_time = time.time() - start_time

            # 将结果转换为字典并添加处理时间
            result_dict = json.loads(result.to_json())
            result_dict["processing_time"] = f"{processing_time:.2f}秒"

            # 添加格式化的响应
            result_dict["formatted_response"] = result.format_response()

            # 添加来源新闻文本
            result_dict["news_text"] = news_text

            return result_dict
        except Exception as e:
            logger.error(f"事实核查过程发生错误: {e}")
            return {
                "error": str(e),
                "status": "failure",
                "processing_time": f"{time.time() - start_time:.2f}秒"
            }

    def check_multiple_sources(self,
                              primary_text: str,
                              additional_sources: List[str] = None,
                              use_images: bool = False) -> Dict[str, Any]:
        """
        分析多个信息源，综合判断真实性

        Args:
            primary_text: 主要信息文本
            additional_sources: 附加信息源列表
            use_images: 是否包含图片证据

        Returns:
            字典格式的综合事实核查结果
        """
        start_time = time.time()

        try:
            # 使用系统进行多源分析
            result = self.system.analyze_multiple_sources(
                news_text=primary_text,
                additional_sources=additional_sources
            )

            # 计算处理时间
            processing_time = time.time() - start_time

            # 将结果转换为字典并添加处理时间
            result_dict = json.loads(result.to_json())
            result_dict["processing_time"] = f"{processing_time:.2f}秒"
            result_dict["source_count"] = 1 + (len(additional_sources) if additional_sources else 0)

            # 添加来源新闻文本
            result_dict["news_text"] = primary_text

            # 添加格式化的响应
            result_dict["formatted_response"] = result.format_response()

            return result_dict
        except Exception as e:
            logger.error(f"多源事实核查过程发生错误: {e}")
            return {
                "error": str(e),
                "status": "failure",
                "processing_time": f"{time.time() - start_time:.2f}秒"
            }

    def retrieve_evidence_only(self,
                             claim: str,
                             use_wiki: bool = True,
                             use_searx: bool = True,
                             use_perplexica: bool = True,
                             use_images: bool = False,
                             save_results: bool = True) -> Dict[str, Any]:
        """
        仅检索证据而不进行真实性判断

        Args:
            claim: 需要检索证据的声明
            use_wiki: 是否使用维基百科
            use_searx: 是否使用Searx搜索引擎
            use_perplexica: 是否使用Perplexica
            use_images: 是否包含图片证据
            save_results: 是否保存检索结果到文件

        Returns:
            字典格式的证据检索结果
        """
        start_time = time.time()
        evidence_list = []

        try:
            # 使用系统的retriever进行检索
            retriever = self.system.retriever

            # 按需从不同来源检索
            if use_searx:
                searx_evidence = retriever.searx_retriever.retrieve_evidence(
                    claim,
                    use_images=use_images,
                    save_results=save_results
                )
                evidence_list.extend(searx_evidence)

            if use_wiki:
                wiki_evidence = retriever.wiki_retriever.retrieve_evidence(
                    claim,
                    save_results=save_results
                )
                evidence_list.extend(wiki_evidence)

            if use_perplexica:
                perplexica_evidence = retriever.perplexica_retriever.retrieve_evidence(
                    claim,
                    chat_model=self.default_chat_model,
                    embedding_model=self.default_embedding_model,
                    save_results=save_results
                )
                evidence_list.extend(perplexica_evidence)

            # 去重并排序
            unique_evidence = retriever._deduplicate_evidence(evidence_list)

            # 保存整合后的所有证据结果
            if save_results and unique_evidence:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                sanitized_claim = claim.replace(" ", "_").replace("/", "_")[:30]
                result_filename = f"all_evidence_{sanitized_claim}_{timestamp}.json"
                results_dir = "search_results"
                if not os.path.exists(results_dir):
                    os.makedirs(results_dir)

                # 构建完整的文件路径
                full_path = os.path.join(results_dir, result_filename)

                evidence_data = {
                    "claim": claim,
                    "timestamp": datetime.now().isoformat(),
                    "total_evidence": len(unique_evidence),
                    "evidence": [
                        {
                            "source": e.source,
                            "title": e.title,
                            "content": e.content,
                            "url": e.url,
                            "relevance": round(e.relevance, 3)
                        }
                        for e in unique_evidence
                    ]
                }

                with open(full_path, 'w', encoding='utf-8') as f:
                    json.dump(evidence_data, f, ensure_ascii=False, indent=2)

                logger.info(f"综合证据结果已保存到: {full_path}")

            # 格式化结果
            evidence_result = {
                "claim": claim,
                "main_claim": claim,  # 添加主要声明字段
                "news_text": claim,   # 添加新闻文本字段
                "verdict": "未评估",   # 添加默认判决
                "confidence": 0.5,    # 添加默认置信度
                "source_count": {
                    "total": len(unique_evidence),
                    "wiki": sum(1 for e in unique_evidence if "wiki" in e.source),
                    "searx": sum(1 for e in unique_evidence if "searx" in e.source),
                    "perplexica": sum(1 for e in unique_evidence if "perplexica" in e.source)
                },
                "evidence": [
                    {
                        "source": e.source,
                        "title": e.title,
                        "content": e.content[:150] + "..." if len(e.content) > 150 else e.content,
                        "url": e.url,
                        "relevance": round(e.relevance, 3)
                    }
                    for e in unique_evidence[:10]  # 最多返回10条
                ],
                "processing_time": f"{time.time() - start_time:.2f}秒"
            }

            return evidence_result
        except Exception as e:
            logger.error(f"证据检索过程发生错误: {e}")
            return {
                "error": str(e),
                "status": "failure",
                "processing_time": f"{time.time() - start_time:.2f}秒"
            }


# 创建单例实例，方便直接导入使用
_default_checker = None

def get_fact_checker(
    searx_host: str = "http://localhost:4000",
    perplexica_port: int = 3001,
    proxy_port: Optional[int] = None,
    perplexica_timeout: int = 120
) -> AdvancedFactChecker:
    """
    获取默认的事实核查器实例（单例模式）

    Args:
        searx_host: SearxNG服务器地址
        perplexica_port: Perplexica API端口号
        proxy_port: 代理端口号
        perplexica_timeout: Perplexica请求超时时间（秒）

    Returns:
        AdvancedFactChecker实例
    """
    global _default_checker

    if _default_checker is None:
        _default_checker = AdvancedFactChecker(
            searx_host=searx_host,
            perplexica_port=perplexica_port,
            proxy_port=proxy_port,
            perplexica_timeout=perplexica_timeout
        )

    return _default_checker


def check_fact(
    news_text: str,
    use_images: bool = False,
    timeout: int = 180,
    proxy_port: Optional[int] = 7890
) -> Dict[str, Any]:
    """
    便捷函数：执行事实核查并返回字典格式的结果

    Args:
        news_text: 新闻文本
        use_images: 是否包含图片证据
        timeout: 超时时间（秒）
        proxy_port: 代理端口号

    Returns:
        字典格式的事实核查结果
    """
    checker = get_fact_checker(proxy_port=proxy_port, perplexica_timeout=timeout)
    return checker.check_fact(news_text=news_text, use_images=use_images, timeout=timeout)


# 使用示例
if __name__ == "__main__":
    import sys

    # 获取命令行参数或使用默认测试声明
    if len(sys.argv) > 1:
        test_claim = sys.argv[1]
    else:
        test_claim = "某国宣布禁用芬太尼后吸毒死亡数下降，成为全球首个完全消除阿片类药物危机的国家。"

    print(f"事实核查: {test_claim}")

    # 使用默认设置进行检查
    result = check_fact(test_claim)

    # 打印结果
    print("\n===== 事实核查结果 =====")
    print(f"判断: {result.get('verdict', '未知')}")
    print(f"置信度: {result.get('confidence', 0)}")
    print(f"主要声明: {result.get('main_claim', '未提取')}")

    # 打印证据摘要
    evidence_list = result.get("evidence", [])
    if evidence_list:
        print(f"\n找到 {len(evidence_list)} 条相关证据，显示前3条:")
        for i, evidence in enumerate(evidence_list[:3], 1):
            print(f"{i}. [{evidence.get('source')}] {evidence.get('title')}")
            print(f"   相关度: {evidence.get('relevance')}")
            print(f"   {evidence.get('content')}")
            if evidence.get('url'):
                print(f"   链接: {evidence.get('url')}")
            print()

    # 打印处理时间
    if "processing_time" in result:
        print(f"处理时间: {result['processing_time']}")


"""
Flask路由集成示例：以下代码展示了如何在Flask应用中使用本模块

将以下代码添加到你的Flask应用中：
"""

"""
from flask import Flask, request, jsonify
import logging
from src.frontend.advanced_fact_check import get_fact_checker, check_fact

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 初始化事实核查器（可以在应用启动时完成）
proxy_port = 7890  # 根据实际情况设置代理端口
fact_checker = get_fact_checker(proxy_port=proxy_port, perplexica_timeout=180)

@app.route('/api/fact-check', methods=['POST'])
def api_fact_check():
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "缺少必需的 'text' 字段"}), 400

        # 从请求参数中获取配置
        news_text = data.get('text')
        use_images = data.get('use_images', False)
        timeout = data.get('timeout', 180)

        # 执行事实核查
        result = fact_checker.check_fact(
            news_text=news_text,
            use_images=use_images,
            timeout=timeout
        )

        return jsonify(result)
    except Exception as e:
        logger.error(f"事实核查API错误: {e}")
        return jsonify({"error": str(e), "status": "failure"}), 500

@app.route('/api/multi-source-check', methods=['POST'])
def api_multi_source_check():
    try:
        data = request.json
        if not data or 'primary_text' not in data:
            return jsonify({"error": "缺少必需的 'primary_text' 字段"}), 400

        # 从请求参数中获取配置
        primary_text = data.get('primary_text')
        additional_sources = data.get('additional_sources', [])
        use_images = data.get('use_images', False)

        # 执行多源事实核查
        result = fact_checker.check_multiple_sources(
            primary_text=primary_text,
            additional_sources=additional_sources,
            use_images=use_images
        )

        return jsonify(result)
    except Exception as e:
        logger.error(f"多源事实核查API错误: {e}")
        return jsonify({"error": str(e), "status": "failure"}), 500

@app.route('/api/evidence-only', methods=['POST'])
def api_evidence_only():
    try:
        data = request.json
        if not data or 'claim' not in data:
            return jsonify({"error": "缺少必需的 'claim' 字段"}), 400

        # 从请求参数中获取配置
        claim = data.get('claim')
        use_wiki = data.get('use_wiki', True)
        use_searx = data.get('use_searx', True)
        use_perplexica = data.get('use_perplexica', True)
        use_images = data.get('use_images', False)
        save_results = data.get('save_results', True)

        # 仅检索证据
        result = fact_checker.retrieve_evidence_only(
            claim=claim,
            use_wiki=use_wiki,
            use_searx=use_searx,
            use_perplexica=use_perplexica,
            use_images=use_images,
            save_results=save_results
        )

        return jsonify(result)
    except Exception as e:
        logger.error(f"证据检索API错误: {e}")
        return jsonify({"error": str(e), "status": "failure"}), 500

# 运行应用（开发环境）
if __name__ == '__main__':
    app.run(debug=True, port=5000)
"""