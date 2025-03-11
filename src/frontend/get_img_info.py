import base64
import json
import re
from zhipuai import ZhipuAI
from pydantic import BaseModel, Field

class ImageDescriptionResponse(BaseModel):
    result: str = Field(..., description="描述是否正确，值为 '正确' 或 '错误'")
    confidence: float = Field(..., ge=0, le=1, description="置信度，范围为 0 到 1")

def parse_content(content: str):
    """
    解析模型返回的内容，提取结果和置信度。
    支持的格式：
    - "正确, 0.95"
    - "错误, 0.85"
    - "描述正确，置信度为 95%"
    - "描述错误，置信度为 85%"
    """
    # 使用正则表达式提取结果和置信度
    result_match = re.search(r"(正确|错误)", content)
    confidence_match = re.search(r"(\d+\.\d+|\d+%)", content)
    
    if not result_match or not confidence_match:
        raise ValueError(f"无法解析模型返回的内容: {content}")
    
    result = result_match.group(1)
    confidence_str = confidence_match.group(1)
    
    # 处理百分数置信度
    if confidence_str.endswith("%"):
        confidence = float(confidence_str.strip("%")) / 100
    else:
        confidence = float(confidence_str)
    
    return result, confidence

def describe_image(img_path, api_key, info):
    # 读取图片并转换为base64编码
    with open(img_path, 'rb') as img_file:
        img_base = base64.b64encode(img_file.read()).decode('utf-8')
    
    # 初始化ZhipuAI客户端
    client = ZhipuAI(api_key=api_key)
    
    # 调用模型进行图片描述
    response = client.chat.completions.create(
        model="glm-4v-flash",  # 填写需要调用的模型名称
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": img_base
                        }
                    },
                    {
                        "type": "text",
                        "text": f"请告诉我我的描述'{info}'是否是这个图片，回答正确或者错误，并告诉我我的描述置信度(0-1)为多少。"
                    }
                ]
            }
        ]
    )
    
    # 解析模型的描述结果
    content = response.choices[0].message.content
    try:
        result, confidence = parse_content(content)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    
    # 创建响应模型并转换为 JSON
    response_model = ImageDescriptionResponse(result=result, confidence=confidence)
    return json.dumps(response_model.model_dump(), ensure_ascii=False)

# # # 示例调用
# img_path = r"D:\Desktop\OIP.jpg"
# api_key = "9e39acc8938cbfb8b86dcd34879e4d5c.oyqOjK1XsrJ0cMgi"
# description_json = describe_image(img_path, api_key, "这是一张海绵宝宝图片")
# print(description_json)