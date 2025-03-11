from text2vec import SentenceModel
import numpy as np

# 加载模型
model = SentenceModel(r"model\models--shibing624--text2vec-base-chinese\snapshots\183bb99aa7af74355fb58d16edf8c13ae7c5433e")

def detect(title,content,threshold=0.55):
    text_embedding = model.encode(content)
    title_embedding = model.encode(title)
    similarity = np.dot(text_embedding, title_embedding) / (np.linalg.norm(text_embedding) * np.linalg.norm(title_embedding))
    if similarity < threshold:
        return 0, similarity  # 返回0表示不符
    else:
        return 1, similarity  # 返回1表示相符

def check_mismatch(title, content, threshold=0.5):
    """
    检测标题和内容是否不符
    :param title: 标题文本
    :param content: 内容文本
    :param threshold: 相似度阈值，默认0.5
    """
    is_mismatch, similarity = detect(title, content, threshold)
    return {
        "title_txt_是否匹配": is_mismatch,
        "title_txt_相似度": float(similarity)  # 将相似度转换为Python float类型
    }

# title = "震惊！科学家发现全新物种，将颠覆生物学！"
# content = """
#     近日，某研究团队在云南山区进行了一次常规生态考察。考察期间，团队成员在海拔2000米的森林中发现了一种小型昆虫。
#     经过初步观察，该昆虫体长约2厘米，身体呈绿色，具有独特的翅膀花纹。团队采集了样本带回实验室进行DNA分析，
#     结果显示该昆虫属于已知的蜻蜓科，但某些基因序列与现有记录存在微小差异。研究人员表示，这一发现对理解蜻蜓科
#     的进化路径有一定参考价值，但尚不足以称为“颠覆生物学”。
#     """
#
# result = check_mismatch(title, content)
# print(f"标题是否不符: {result['is_mismatch']}")
# print(f"相似度: {result['similarity']:.2f}")