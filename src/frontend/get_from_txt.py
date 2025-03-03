import os
import json
from openai import OpenAI
from pydantic import BaseModel  # 用于结构化数据验证

# 定义数据模型
class Article(BaseModel):
    title: str
    content: str
    category: str
    keywords: list[str] = []
    publish_date: str | None = None

def extract_news_info(text: str, api_key: str) -> dict | None:
    """
    使用 OpenAI GPT-4o-mini 从新闻文本中提取结构化信息
    参数：
        text: 原始新闻文本（包含标题和正文）
        api_key: OpenAI API 密钥
    返回：
        格式化后的 JSON 数据，若失败则返回 None
    """
    # 初始化 OpenAI 客户端
    client = OpenAI(api_key=api_key, base_url='https://api.chatanywhere.tech')

    # 构造带结构化指令的提示词
    prompt = f"""请从以下新闻文本中提取结构化信息：
    {text}

    需要提取的字段：
    1. title（标题）：简明扼要的核心标题
    2. content（正文）：去除冗余信息的纯文本内容
    3. category（类别）：从[科技/财经/政治/娱乐/体育/社会]中选择最匹配的分类
    4. keywords（关键词）：3-5个核心关键词
    5. publish_date（发布日期）：格式YYYY-MM-DD（如无明确日期则留空）

    请以JSON格式返回，确保字段类型正确且无语法错误。"""

    try:
        # 调用 OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # 使用 GPT-4 模型
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},  # 强制 JSON 输出格式
            temperature=0.3  # 控制输出稳定性
        )

        # 解析并验证结果
        raw_data = json.loads(response.choices[0].message.content)
        validated_data = Article(**raw_data).model_dump()  # 使用 model_dump 替代 dict

        # 返回格式化后的 JSON 数据
        return json.dumps(validated_data, 
                         indent=4, 
                         ensure_ascii=False,
                         sort_keys=False)

    except Exception as e:
        print(f"处理失败：{str(e)}")
        return None

def save_to_json(data: str, filename: str = "output.json") -> None:
    """
    将数据保存为 JSON 文件
    参数：
        data: 要保存的 JSON 数据
        filename: 保存的文件名
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(data)
        print(f"数据已成功保存到 {filename}")
    except Exception as e:
        print(f"保存文件失败：{str(e)}")

# 使用示例
if __name__ == "__main__":
    # 示例新闻文本
    news_text = """2025年3月2日，科技前沿——OpenAI今日宣布推出新一代语言模型GPT-5。该模型在自然语言处理领域取得了重大突破，预计将广泛应用于教育、医疗和金融等行业。发布会上，OpenAI CEO Sam Altman表示，GPT-5将进一步提升人工智能的理解和生成能力。"""

    # 设置 OpenAI API 密钥（建议从环境变量中读取）
    api_key = os.getenv("OPENAI_API_KEY", "your-api-key")

    # 提取信息
    result = extract_news_info(news_text, api_key)
    if result:
        # 打印结果
        print(result)
        # 保存为 JSON 文件
        save_to_json(result, "news_output.json")