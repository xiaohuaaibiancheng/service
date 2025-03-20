import torch
import numpy as np
import jieba
import re
import time
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
)
from sklearn.metrics import accuracy_score

# 1. 加载训练好的模型和分词器
model_path = r"D:\project\service\main\model\a"
model = AutoModelForSequenceClassification.from_pretrained(model_path)
tokenizer = AutoTokenizer.from_pretrained("nghuyong/ernie-3.0-base-zh")

# 2. 数据预处理模块
# Clean text: remove special characters and punctuation
def clean_text(text):
    # Remove non-Chinese characters and punctuation
    text = re.sub(r'[^\w\s\u4e00-\u9fa5]', '', text)
    return text

# Remove stopwords
def remove_stopwords(text, stopwords):
    words = list(jieba.cut(text))  # Tokenize
    words = [word for word in words if word not in stopwords]
    return ' '.join(words)

# Load stopwords
def load_stopwords():
    stopwords = set()
    with open(r"D:\project\service\测试\chinese.txt", 'r', encoding='utf-8') as file:
        for line in file.readlines():
            stopwords.add(line.strip())
    return stopwords

# 加载停用词
stopwords = load_stopwords()

# 3. 定义单个测试数据
single_text = "这是一个测试句子。"

# 4. 对单个数据进行预处理
def preprocess_single_text(text):
    # 清理文本
    cleaned_text = clean_text(text)
    # 去除停用词
    preprocessed_text = remove_stopwords(cleaned_text, stopwords)
    return preprocessed_text

preprocessed_text = preprocess_single_text(single_text)
start_time = time.time()  # 开始计时
# 5. 对预处理后的文本进行分词
encoded_text = tokenizer(
    preprocessed_text, 
    truncation=True, 
    max_length=256,  # 与测试集相同的最大长度
    return_tensors="pt"  # 返回 PyTorch 张量
)

# 6. 使用模型进行推理并记录时间
model.eval()  # 将模型设置为评估模式
with torch.no_grad():
    outputs = model(**encoded_text)
    logits = outputs.logits
end_time = time.time()  # 结束计时
inference_time = end_time - start_time  # 计算推理时间

# 7. 处理推理结果
predicted_label = torch.argmax(logits, dim=-1).item()

# 8. 输出预测结果和推理时间
print(f"预测的标签: {predicted_label}")
print(f"推理时间: {inference_time:.4f} 秒")