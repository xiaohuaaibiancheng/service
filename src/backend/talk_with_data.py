import os
import json
import logging
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from llama_index.llms.openai import OpenAI
from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.schema import Document
from llama_index.embeddings.huggingface import HuggingFaceEmbedding  # 本地嵌入模型
from llama_index.core import StorageContext, load_index_from_storage
# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 定义配置
CONFIG = {
    "data_path": Path("src/static/backend/output_data.json"),  # 数据文件路径
    "index_persist_dir": Path("src/static/backend/storage"),  # 索引持久化目录
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "openai_api_base": "https://api.chatanywhere.tech",  # 自定义 API 端点
    "model": "gpt-3.5-turbo",
    "temperature": 0.1,
    "chunk_size": 512,
}

# 使用本地嵌入模型
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-zh-v1.5",device="cuda")

# 加载新闻数据
def load_news_data(file_path: Path) -> List[Document]:
    """加载并解析新闻数据"""
    documents = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            news_list = json.load(f)
            for news in news_list:
                # 构建结构化文本
                text_parts = [
                    f"新闻 ID：{news['news_id']}",
                    f"标题：{news['title']}",
                    f"发布时间：{news['publish_time']}",
                    f"平台：{news['platform']}",
                    f"标签：{news['label']}",
                    f"可信度评分：{news['credibility']['score']}",
                    "可信度维度评分："
                    f"- 来源可信度：{news['credibility']['dimension_scores']['source']}",
                    f"- 内容可信度：{news['credibility']['dimension_scores']['content']}",
                    f"- 逻辑合理性：{news['credibility']['dimension_scores']['logic']}",
                    "\n传播情况："
                ]

                # 处理传播时间线
                for timeline in news['propagation']['timeline']:
                    text_parts.append(
                        f"{timeline['timestamp']} 在 {timeline['platform']} 平台传播，"
                        f"分享 {timeline['shares']} 次，地区分布：{', '.join([f'{k}({v})' for k, v in timeline['geo_distribution'].items()])}"
                    )

                # 添加用户画像
                text_parts.extend([
                    "\n用户画像：",
                    f"年龄分布：{json.dumps(news['propagation']['user_profile']['age_dist'], ensure_ascii=False)}",
                    f"设备比例：{json.dumps(news['propagation']['user_profile']['device_ratio'], ensure_ascii=False)}"
                ])

                # 添加关联信息
                if news['relations']:
                    text_parts.extend([
                        "\n关联信息：",
                        f"相关谣言：{', '.join(news['relations']['related_rumors'])}",
                        f"知识节点：{', '.join(news['relations']['knowledge_nodes'])}"
                    ])

                # 合并所有文本部分
                full_text = "\n".join(text_parts)
                documents.append(Document(text=full_text))
        logger.info("成功加载新闻数据，共 %d 条", len(documents))
    except Exception as e:
        logger.error(f"加载新闻数据失败：{str(e)}")
        raise
    return documents

# 初始化或加载索引
def initialize_news_index() -> VectorStoreIndex:
    """初始化或加载持久化索引"""
    try:
        if CONFIG["index_persist_dir"].exists() and any(CONFIG["index_persist_dir"].iterdir()):
            storage_context = StorageContext.from_defaults(persist_dir=CONFIG["index_persist_dir"])
            index = load_index_from_storage(storage_context)
            logger.info("从持久化存储加载新闻索引")
        else:
            # 重新构建索引并持久化
            news_docs = load_news_data(CONFIG["data_path"])
            index = VectorStoreIndex.from_documents(news_docs)
            index.storage_context.persist(persist_dir=CONFIG["index_persist_dir"])
            logger.info("新闻索引构建完成，已保存到 %s", CONFIG["index_persist_dir"])
        logger.info("当前索引包含 %d 条数据", len(index.docstore.docs))
        return index
    except Exception as e:
        logger.error(f"初始化索引失败：{str(e)}")
        raise

# 初始化 OpenAI 服务
def initialize_openai_llm() -> OpenAI:
    """初始化 OpenAI 服务"""
    try:
        llm = OpenAI(
            temperature=CONFIG["temperature"],
            model=CONFIG["model"],
            api_key=CONFIG["openai_api_key"],
            api_base=CONFIG["openai_api_base"]
        )
        logger.info("OpenAI 服务初始化成功")
        return llm
    except Exception as e:
        logger.error(f"初始化 OpenAI 服务失败：{str(e)}")
        raise

# 主函数
def main():
    """主函数"""
    try:
        # 初始化全局配置
        Settings.llm = initialize_openai_llm()
        Settings.chunk_size = CONFIG["chunk_size"]

        # 初始化索引
        index = initialize_news_index()

        # 创建查询引擎
        query_engine = index.as_query_engine(similarity_top_k=3)

        # 示例查询
        queries = [
            "关于'离婚窗口排长队'的传播情况有哪些关键数据？",
            "哪些地区的用户最活跃？",
            "这条新闻的可信度评分依据是什么？"
        ]

        for query in queries:
            response = query_engine.query(query)
            print(f"问题：{query}")
            print(f"回答：{response}\n{'-'*50}\n")
    except Exception as e:
        logger.error(f"程序运行失败：{str(e)}")

# 程序入口
if __name__ == "__main__":
    main()