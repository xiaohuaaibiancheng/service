import os
import json
import logging
from pathlib import Path
import shutil
from tqdm import tqdm  # 添加进度条
from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.schema import Document
from llama_index.embeddings.huggingface import HuggingFaceEmbedding  # 本地嵌入模型

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 定义路径
DATA_PATH = Path("src/static/backend/output_data.json")  # 数据文件路径
INDEX_PERSIST_DIR = Path("src/static/backend/storage")  # 索引持久化目录

# 加载新闻数据
def load_news_data(file_path: Path):
    """加载并解析新闻数据"""
    documents = []
    with open(file_path, "r", encoding="utf-8") as f:
        news_list = json.load(f)

        # 添加进度条
        for news in tqdm(news_list, desc="加载新闻数据"):
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

    return documents

# 初始化或加载索引
def initialize_news_index():
    """初始化或加载持久化索引"""
    global news_index

    # 使用本地嵌入模型（针对中文优化）
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-zh-v1.5")

    # 如果存在持久化索引，直接加载
    if INDEX_PERSIST_DIR.exists() and any(INDEX_PERSIST_DIR.iterdir()):
        storage_context = StorageContext.from_defaults(persist_dir=INDEX_PERSIST_DIR)
        news_index = VectorStoreIndex.load_index_from_storage(storage_context)
        logger.info("从持久化存储加载新闻索引")
    else:
        # 重新构建索引并持久化
        news_docs = load_news_data(DATA_PATH)
        logger.info("开始构建新闻索引...")
        news_index = VectorStoreIndex.from_documents(news_docs)
        news_index.storage_context.persist(persist_dir=INDEX_PERSIST_DIR)
        logger.info("新闻索引构建完成，已保存到 %s", INDEX_PERSIST_DIR)

    logger.info("当前索引包含 %d 条数据", len(news_index.docstore.docs))

# 清除持久化索引
def clear_index():
    """清除持久化索引"""
    if INDEX_PERSIST_DIR.exists():
        shutil.rmtree(INDEX_PERSIST_DIR)
    logger.info("已清除持久化索引")

clear_index()
# 初始化索引
initialize_news_index()