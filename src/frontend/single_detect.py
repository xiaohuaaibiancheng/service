from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import torch
import os
import json

# 设置离线模式环境变量
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# 加载模型和分词器
LOCAL_MODEL_PATH = "model/new_model"  # 或 "./new_model" 如果您已经训练完成

model = AutoModelForSequenceClassification.from_pretrained(
    LOCAL_MODEL_PATH, 
    local_files_only=True
)
tokenizer = AutoTokenizer.from_pretrained(
    'model/tokenizer',
    local_files_only=True
)


# 创建推理管道
classifier = pipeline(
    "text-classification",
    model=model,
    tokenizer=tokenizer,
    device=0 if torch.cuda.is_available() else -1
)

def predict_rumor(text):
    """
    预测输入的文本是否为谣言或事实
    :param text: 输入的文本
    :return: 预测结果的 JSON 格式，包含类别和概率
    """
    # 对输入文本进行推理
    prediction = classifier(text)
    
    # 提取预测结果
    predicted_label = int(prediction[0]['label'].split('_')[-1])  # 类别标签
    predicted_prob = prediction[0]['score']  # 概率值
    
    # 定义标签映射
    label_map = {0: "谣言", 1: "事实"}
    
    # 返回预测结果的 JSON 格式
    result = {
        "text": text,
        "predicted_label": label_map[predicted_label],
        "probability": predicted_prob
    }
    
    return json.dumps(result, ensure_ascii=False)

# 示例调用
if __name__ == "__main__":
    text = "这是一个测试标题"
    result = predict_rumor(text)
    print(result)