import torch
from PIL import Image
from transformers import AutoFeatureExtractor, AutoModelForImageClassification

def classify_image(image_path):
    # 加载图片
    image = Image.open(image_path)

    # 定义标签
    labels = ["真实", "AI"]

    # 加载特征提取器和模型
    feature_extractor = AutoFeatureExtractor.from_pretrained(
        r"model\models--Nahrawy--AIorNot\snapshots\569e9f0798e4b20f10c3ec408e32c2316b9fa0bb",
    )
    model = AutoModelForImageClassification.from_pretrained(
        r"model\models--Nahrawy--AIorNot\snapshots\569e9f0798e4b20f10c3ec408e32c2316b9fa0bb",
    )

    # 预处理图片
    input = feature_extractor(image, return_tensors="pt")

    # 推理
    with torch.no_grad():
        outputs = model(**input)
        logits = outputs.logits

    # 将 logits 转换为概率
    probabilities = torch.softmax(logits, dim=-1).squeeze().tolist()

    # 获取预测结果
    prediction = logits.argmax(-1).item()
    label = labels[prediction]
    predicted_prob = probabilities[prediction]  # 预测类别的概率

    return label, predicted_prob

if __name__ == "__main__":
    # 示例用法
    image_path = r"D:\Desktop\16336d3c-f9d5-48a5-b621-ce3dcfed4d1c.jpg"  # 替换为你的图片路径
    result, prob = classify_image(image_path)
    print(f"预测类别: {result}, 预测概率: {prob:.4f}")