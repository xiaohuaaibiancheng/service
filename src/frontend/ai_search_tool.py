import json
import os
import logging
import requests
import traceback
from typing import Dict, List, Optional, Any, Union
from flask import current_app
import openai

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AISearchTool:
    """集成AI搜索和OpenAI总结功能的工具"""
    
    def __init__(self, perplexica_port: int = 3001, proxy_port: Optional[int] = None):
        """
        初始化AI搜索工具
        
        Args:
            perplexica_port: Perplexica API端口号 (默认3001)
            proxy_port: 代理端口号 (可选)
        """
        self.port = perplexica_port
        self.proxies = None
        if proxy_port:
            self.proxies = {
                "http": f"http://127.0.0.1:{proxy_port}",
                "https": f"http://127.0.0.1:{proxy_port}"
            }
        self.timeout = 60  # 默认超时时间为60秒
        logger.info(f"初始化AI搜索工具: Perplexica端口={perplexica_port}, 代理端口={proxy_port}")
    
    def search(self, query: str, focus_mode: str = "webSearch") -> Optional[Dict[str, Any]]:
        """
        执行搜索查询
        
        Args:
            query: 搜索查询内容
            focus_mode: 搜索模式 (webSearch/academicSearch等)
            
        Returns:
            API响应字典或None
        """
        logger.info(f"执行搜索: 查询='{query}', 模式='{focus_mode}'")
        url = f"http://localhost:{self.port}/api/search"
        
        # 构建请求载荷
        payload = {
            "focusMode": focus_mode,
            "query": query
        }
        
        try:
            logger.debug(f"发送请求到 {url}")
            response = requests.post(url, json=payload, proxies=self.proxies, timeout=self.timeout)
            response.raise_for_status()
            logger.info("搜索请求成功")
            return response.json()
        except Exception as err:
            logger.error(f"搜索请求失败: {err}")
            logger.debug(traceback.format_exc())
            return None
    
    def summarize_with_openai(self, search_response: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        使用OpenAI总结搜索结果
        
        Args:
            search_response: Perplexica搜索响应
            query: 原始查询内容
            
        Returns:
            带有AI总结和判断的增强响应
        """
        try:
            # 如果没有获得有效响应
            if not search_response or "message" not in search_response:
                return {"summary": "无法获取有效的搜索结果", "judgment": "不确定", "original_response": search_response}
            
            # 提取搜索结果和来源
            search_message = search_response.get("message", "")
            sources = search_response.get("sources", [])
            
            # 构建用于总结的提示词
            sources_text = []
            for i, source in enumerate(sources, 1):
                meta = source.get("metadata", {})
                title = meta.get("title", "无标题")
                url = meta.get("url", "无链接")
                content = source.get("pageContent", "无内容")[:300]
                
                sources_text.append(f"来源{i} - {title} ({url}):\n{content}...")
            
            sources_combined = "\n\n".join(sources_text)
            
            # 使用OpenAI API进行总结
            api_key = current_app.config.get('OPENAI_API_KEY') if current_app else os.environ.get('OPENAI_API_KEY')
            base_url = current_app.config.get('OPENAI_BASE_URL') if current_app else os.environ.get('OPENAI_BASE_URL')
            
            if not api_key:
                return {"summary": "无法获取OpenAI API密钥", "judgment": "不确定", "original_response": search_response}
            
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            
            prompt = f"""
            用户查询: {query}
            
            搜索结果: {search_message}
            
            信息来源:
            {sources_combined}
            
            请提供:
            1. 简洁的总结 (150字以内)
            2. 信息可靠性判断 (可靠/部分可靠/不可靠/不确定)
            3. 判断理由 (50字以内)
            
            请确保回答使用中文。
            """
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是一个专业信息分析师，负责分析搜索结果并提供简洁的总结和可靠性判断。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            summary = response.choices[0].message.content
            
            # 解析AI输出，提取判断结果
            judgment = "不确定"
            if "可靠" in summary:
                if "不可靠" in summary:
                    judgment = "不可靠"
                elif "部分可靠" in summary:
                    judgment = "部分可靠" 
                else:
                    judgment = "可靠"
            
            return {
                "summary": summary,
                "judgment": judgment,
                "original_response": search_response
            }
            
        except Exception as err:
            logger.error(f"OpenAI总结失败: {err}")
            logger.debug(traceback.format_exc())
            return {
                "summary": f"AI总结处理过程中出错: {str(err)}",
                "judgment": "错误",
                "original_response": search_response
            }
    
    def search_and_summarize(self, query: str, focus_mode: str = "webSearch") -> Dict[str, Any]:
        """
        执行搜索并用AI总结结果
        
        Args:
            query: 搜索查询内容
            focus_mode: 搜索模式 (webSearch/academicSearch等)
            
        Returns:
            包含搜索结果、AI总结和判断的响应
        """
        search_result = self.search(query, focus_mode)
        if not search_result:
            return {"error": "搜索失败", "details": "无法获取搜索结果"}
        
        return self.summarize_with_openai(search_result, query)
    
    @staticmethod
    def format_result_html(result: Dict[str, Any]) -> str:
        """
        将搜索和总结结果格式化为HTML展示
        
        Args:
            result: 搜索和总结结果
            
        Returns:
            格式化的HTML字符串
        """
        if "error" in result:
            return f"<div class='error'><h3>错误</h3><p>{result['error']}</p><p>{result.get('details', '')}</p></div>"
        
        original_response = result.get("original_response", {})
        sources = original_response.get("sources", [])
        message = original_response.get("message", "无内容")
        summary = result.get("summary", "无总结")
        judgment = result.get("judgment", "不确定")
        
        # 为判断结果设置颜色
        judgment_color = "#666666"  # 默认灰色
        if judgment == "可靠":
            judgment_color = "#28a745"  # 绿色
        elif judgment == "部分可靠":
            judgment_color = "#ffc107"  # 黄色
        elif judgment == "不可靠":
            judgment_color = "#dc3545"  # 红色
        
        # 处理引用标记
        for i, _ in enumerate(sources, 1):
            citation = f"[{i}]"
            tooltip_html = f'<span class="citation" data-source-id="{i}" onclick="showSource({i})">{citation}</span>'
            message = message.replace(citation, tooltip_html)
        
        html = [
            '<div class="ai-search-result">',
            f'<div class="judgment" style="background-color: {judgment_color}; color: white; padding: 8px 15px; border-radius: 4px; display: inline-block; margin-bottom: 15px;">',
            f'<strong>AI判断:</strong> {judgment}',
            '</div>',
            '<div class="summary">',
            '<h3>🤖 AI总结与分析:</h3>',
            f'<p>{summary}</p>',
            '</div>',
            '<div class="answer">',
            '<h3>📖 搜索结果:</h3>',
            f'<p>{message}</p>',
            '</div>'
        ]
        
        # 添加来源信息
        if sources:
            html.append('<div class="sources">')
            html.append('<h3>🔍 信息来源:</h3>')
            html.append('<div class="source-list">')
            
            for i, source in enumerate(sources, 1):
                meta = source.get("metadata", {})
                title = meta.get("title", "无标题")
                url = meta.get("url", "无链接")
                content = source.get("pageContent", "无内容")[:200]
                
                html.append(f'<div id="source-{i}" class="source-item">')
                html.append(f'<h4><a href="{url}" target="_blank">{i}. {title}</a></h4>')
                html.append(f'<p class="content-preview">{content}...</p>')
                html.append('</div>')
            
            html.append('</div>')  # 关闭source-list
            html.append('</div>')  # 关闭sources
        
        html.append('</div>')  # 关闭ai-search-result
        
        return '\n'.join(html) 