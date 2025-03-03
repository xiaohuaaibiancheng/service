# 安装依赖库
# pip install docling openai langchain langchain-openai

import os
from docling.document_converter import DocumentConverter
import json


# 初始化 Docling 文档转换器
converter = DocumentConverter()

# 解析文档（支持 PDF/DOCX/PPTX 等格式）
def parse_document(file_path):
    try:
        # 解析文档
        result = converter.convert(file_path)
        # 导出为结构化字典
        doc_json = result.document.export_to_dict()
        print(doc_json)
        return doc_json
    except Exception as e:
        print(f"文档解析失败: {e}")
        return None

# 自定义结构化数据处理
def structure_data(doc_json):
    # 输入验证
    if not isinstance(doc_json, dict) or 'texts' not in doc_json:
        raise ValueError("Invalid input: doc_json must be a dictionary with a 'texts' key.")

    # 提取标题（如果为空，使用默认值）
    title = doc_json['texts'][0]['text'].strip() if doc_json['texts'] else "Untitled"

    # 提取内容（过滤空段落并拼接为完整字符串）
    content = " ".join(item['text'].strip() for item in doc_json['texts'][1:] if item['text'].strip())

    # 返回结构化数据
    structured_data = {
        "title": title,
        "content": content,  # 返回完整字符串
    }
    return structured_data





# 主函数
def get_file_content(file_path):
    # 解析文档
    doc_json = parse_document(file_path)
    if not doc_json:
        return

    # 结构化数据处理
    structured_data = structure_data(doc_json)
    if not structured_data:
        return {
        "title": '提取失败',
        "content":'提取失败',
    }
    return structured_data





# 运行主函数
if __name__ == "__main__":
    # 输入参数
    file_path = r"D:\Desktop\二月二舞动千年龙魂.docx"  # 替换为你的文档路径

    # 执行主函数
    get_file_content(file_path)