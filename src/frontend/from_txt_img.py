import torch
from PIL import Image
import json
import cn_clip.clip as clip
from cn_clip.clip import load_from_name

class ImageTextSimilarity:
    def __init__(self, model_name="ViT-B-16", device=None, download_root='./model'):
        """
        初始化模型和预处理函数。
        
        :param model_name: 模型名称，默认为 'ViT-B-16'
        :param device: 设备类型，'cuda' 或 'cpu'，默认为自动检测
        :param download_root: 模型下载路径，默认为 './'
        """
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model, self.preprocess = load_from_name(model_name, device=self.device, download_root=download_root)
        self.model.eval()

    def calculate_similarity(self, image_path, text):
        """
        计算图像和文本之间的相似度概率。
        
        :param image_path: 图像文件路径
        :param text: 输入的文本
        :return: JSON 对象，包含相似度概率
        """
        # 加载图像并预处理
        image = self.preprocess(Image.open(image_path)).unsqueeze(0).to(self.device)

        # 对文本进行 tokenize
        text_tokens = clip.tokenize([text]).to(self.device)

        # 提取图像和文本特征
        with torch.no_grad():
            image_features = self.model.encode_image(image)
            text_features = self.model.encode_text(text_tokens)
            
            # 归一化特征
            image_features /= image_features.norm(dim=-1, keepdim=True) 
            text_features /= text_features.norm(dim=-1, keepdim=True)    

            # 计算相似度
            logits_per_image = (image_features @ text_features.T).softmax(dim=-1)
            similarity_prob = logits_per_image.cpu().numpy()[0][0]

        # 返回 JSON 结果
        result = {
            "text": text,  # 直接使用原始文本，而不是张量
            "image_path": image_path,
            "text_pic_similarity_probability": float(similarity_prob)
        }
        return result
    
if __name__=='__main__':
      # 初始化类
  classifier = ImageTextSimilarity(model_name="ViT-B-16")

  # 计算相似度
  image_path = "D:\Desktop\OIP.jpg"
  text = "这是一张可爱的皮卡丘图片"
  result = classifier.calculate_similarity(image_path, text)

  # 打印结果
  print(result)