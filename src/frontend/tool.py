import csv
from datetime import datetime
import json
import sys
from bs4 import BeautifulSoup
import logging
from newspaper import Article
import os
import requests
import torch
from werkzeug.utils import secure_filename
import yaml
from src.frontend.TTmatch import check_mismatch
from src.frontend.get_file_content import get_file_content
from src.frontend.get_from_txt import extract_news_info, save_to_json
from transformers import BertTokenizerFast
from torchvision import transforms
from PIL import Image
from newspaper import Article, ArticleException

# 导入配置
from src.config import OPENAI_API_KEY, IMAGE_API_KEY

from src.frontend.get_img_info import describe_image
os.environ["DISABLE_CUSTOM_KERNELS"] = "1"
def detect_fake_news(content):
    """模拟检测新闻真伪"""
    # 从配置中获取API密钥
    api_key = OPENAI_API_KEY

    # 提取信息
    result = extract_news_info(content, api_key)

    if result:
        # 打印结果
        print(result)
        # 保存为 JSON 文件
        save_to_json(result, "news_output.json")
    
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
def is_valid_image_url(url):
    """
    检查图片 URL 是否有效。
    :param url: 图片的 URL
    :return: True 如果有效，False 如果无效
    """
    try:
        # 发送 HEAD 请求，检查 URL 是否存在
        response = requests.head(url, timeout=5)
        if response.status_code != 200:
            return False

        # 下载图片，检查是否为有效图片
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return False

        # 使用 PIL 打开图片，检查是否为有效图片
        try:
            image = Image.open(BytesIO(response.content))
            image.verify()  # 验证图片是否损坏
            if image.width < 50 or image.height < 50:  # 过滤掉尺寸过小的图片
                return False
            return True
        except Exception:
            return False
    except requests.exceptions.RequestException:
        return False

def filter_image_urls(image_urls):
    """
    过滤掉无效的图片 URL。
    :param image_urls: 图片 URL 列表
    :return: 过滤后的图片 URL 列表
    """
    valid_images = []
    for url in image_urls:
        if is_valid_image_url(url):
            valid_images.append(url)
        else:
            logging.info(f"过滤掉无效图片 URL: {url}")
    return valid_images
def extract_and_detect_url_news(url, classifier_txt_img):
    try:
        # 初始化 Article 对象
        article = Article(url)
        
        # 下载并解析文章
        article.download()
        article.parse()
        article.nlp()

        # 提取新闻属性
        title = article.title or "无标题"
        text = article.text or "无正文内容"
        publish_date = article.publish_date or datetime.now()  # 如果无日期，使用当前时间
        authors = article.authors or ["未知作者"]
        images = list(article.images) or []
        videos = list(article.movies) or []
        summary = article.summary or "无摘要"
        keywords = article.keywords or []
        source_url = article.source_url or url
        language = article.meta_lang or "未知语言"
        meta_data = article.meta_data or {}
        html_content = article.html or ""
        tags = list(article.tags) or []

        # 验证提取的内容
        if not text.strip() or text == "无正文内容":
            logging.warning(f"URL {url} 的正文内容为空，可能是解析失败。")
        
            # 如果需要，可以使用 BeautifulSoup 进一步提取 HTML 内容
            soup = BeautifulSoup(html_content, "html.parser")
            text = soup.get_text(separator="\n").strip()
            if not text:
                logging.error(f"URL {url} 无法提取到正文内容，即使使用 BeautifulSoup 也失败。")
                return {"error": "解析失败，请重试或者直接输入内容"}

        # 打印提取的信息
        logging.info("提取的新闻信息：")
        logging.info(f"标题: {title}")
        logging.info(f"正文: {text[:100]}...")  # 打印前 100 个字符
        logging.info(f"发布日期: {publish_date}")
        logging.info(f"作者: {authors}")
        logging.info(f"图片: {images}")
        logging.info(f"视频: {videos}")
        logging.info(f"摘要: {summary}")
        logging.info(f"关键词: {keywords}")
        logging.info(f"来源 URL: {source_url}")
        logging.info(f"语言: {language}")
        logging.info(f"元数据: {meta_data}")
        logging.info(f"HTML 内容: {html_content[:100]}...")  # 打印前 100 个字符
        logging.info(f"标签: {tags}")
        images = filter_image_urls(images)
        # 根据内容进行处理
        if images and text and title:
            result1=process_image_and_text(images, text, classifier_txt_img)
            result2=process_title_and_text(title, text)
            result=result1.update(result2)
        elif images and text:
            result = process_image_and_text(images, text, classifier_txt_img)
        elif title and text:
            result = process_title_and_text(title, text)
        elif text:
            result = process_text_only(text)
        else:
            return {"error": "无效的输入组合"}

        # 返回结果
        return result

    except ArticleException as e:
        logging.error(f"newspaper3k 解析失败: {str(e)}")
        return {"error": f"无法解析 URL: {str(e)}"}
    except requests.exceptions.RequestException as e:
        logging.error(f"下载 URL 失败: {str(e)}")
        return {"error": f"无法下载 URL: {str(e)}"}
    except Exception as e:
        logging.error(f"未知错误: {str(e)}")
        return {"error": f"未知错误: {str(e)}"}



def extract_and_detect_file_news(file_path_or_url):
    try:
        content=get_file_content(file_path_or_url)
        print(content)
        title=content['title']
        text=content['content']
        if title and text:
            result = process_title_and_text(title, text)
        
        
        # 返回结果
        return result
    except Exception as e:
        # 捕获并处理异常，返回错误信息
        return {
            "error": f"An error occurred while processing the file/URL: {str(e)}"
        }
    
def process_image_and_text(image, text, model):
    # 处理图片和文本的逻辑
    # 这里可以保存图片、处理图片和文本的关系等
    print(11111)
    # 判断图片是文件上传、本地路径还是URL
    if hasattr(image, 'filename'):  # 文件上传
        image_filename = secure_filename(image.filename)
        image_filename='upload.'+image_filename
        print('image_filename',image_filename)
        image_path = os.path.join('uploads', image_filename)
        print('image_path',image_path)
        image.save(image_path)
    elif isinstance(image[0], str) and image[0].startswith(('http://', 'https://')):  # URL
        response = requests.get(image[0])
        if response.status_code == 200:
            image_path = os.path.join('uploads', 'downloaded_image.jpg')
            with open(image_path, 'wb') as f:
                f.write(response.content)
        else:
            raise ValueError("Failed to download image from URL")
    else:  # 本地路径
        if os.path.exists(image):
            image_path = image
        else:
            raise FileNotFoundError(f"Image file not found at {image}")

    # # 保存图片
    # image_path = image
    
    # 使用配置中的API密钥
    api_key = IMAGE_API_KEY
    description_json_str = describe_image(image_path, api_key, text)

    description_json = json.loads(description_json_str)
    # 计算图片和文本的相似度
    # result = model.calculate_similarity(image_path, text)
    # result['text_pic_similarity_probability']=description_json['confidence']
    confidence = description_json.get("confidence")
    result = {
    "text": text,  # 直接使用原始文本，而不是张量
    "image_path": image_path,
    "text_pic_similarity_probability": confidence
}
    return result

def process_title_and_text(title, text):
    # 处理标题和文本的逻辑
    # 这里可以将标题和文本关联起来
    #文题一致检测
    result=check_mismatch(title,text)
    return result

def process_text_only(text):
    # 处理只有文本的逻辑
    # 这里可以将部分文本当作标题
    title = text[:50]  # 假设前50个字符作为标题
    result=check_mismatch(title,text)
    return result

current_dir = os.path.dirname(os.path.abspath(__file__))
multimodal_path = os.path.join(current_dir, 'MultiModal_DeepFake_main')
if multimodal_path not in sys.path:
    sys.path.append(multimodal_path)
from src.frontend.MultiModal_DeepFake_main.models.HAMMER import HAMMER
def init_hammer_model():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 读取配置文件
    config_path = os.path.join(multimodal_path, 'configs', 'test.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 使用 configs/config_bert.json
    config['bert_config'] = os.path.join(multimodal_path, 'configs', 'config_bert.json')
    # 设置 BERT 模型路径
    bert_path = os.path.join(multimodal_path, 'bert-base-uncased')
    
    # 初始化模型
    model = HAMMER(
        config=config,
        text_encoder=bert_path  # 加载 BERT 权重
    )
    
    # 加载 ALBEF 预训练权重
    albef_path = os.path.join(multimodal_path, 'ALBEF_4M.pth')
    if os.path.exists(albef_path):
        checkpoint = torch.load(albef_path, map_location=device)
        model_dict = model.state_dict()
        # 加载所有匹配的权重（包括视觉和文本）
        pretrained_dict = {k: v for k, v in checkpoint.items() if k in model_dict}
        model_dict.update(pretrained_dict)
        model.load_state_dict(model_dict, strict=False)
        print("Loaded ALBEF weights")
    
    model = model.to(device)
    model.eval()
    
    # 初始化tokenizer
    tokenizer = BertTokenizerFast.from_pretrained(os.path.join(multimodal_path, 'bert-base-uncased'))
    
    # 初始化图像转换
    transform = transforms.Compose([
        transforms.Resize((config['image_res'], config['image_res'])),  # 使用配置文件中的尺寸
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    return model, tokenizer, transform


# 第三个功能：多模态图片和文本检测
def analyze_media(image_path, text,transform,tokenizer,model):
    print(3)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 从文件路径加载图像
    img = Image.open(image_path).convert('RGB')
    
    # 处理图像
    img_tensor = transform(img).unsqueeze(0).to(device)
    text_inputs = tokenizer(
        [text], 
        max_length=128,
        padding='max_length',
        truncation=True,
        return_tensors='pt'
    ).to(device)
    
    # 模型推理
    with torch.no_grad():
        logits_real_fake, logits_multicls, output_coord, logits_tok = model(
            img_tensor, None, text_inputs, None, None, alpha=0, is_train=False
        )
        pred_probs = F.softmax(logits_real_fake, dim=1)
        is_fake = pred_probs[0][1].item() > 0.5
        result = {
            'is_fake': bool(is_fake),
            'fake_probability': f"{pred_probs[0][1].item() * 100:.1f}%",
            'real_probability': f"{pred_probs[0][0].item() * 100:.1f}%",
            'manipulation_types': {
                'face_swap': f"{F.sigmoid(logits_multicls[0][0]).item() * 100:.1f}%",
                'face_attribute': f"{F.sigmoid(logits_multicls[0][1]).item() * 100:.1f}%",
                'text_swap': f"{F.sigmoid(logits_multicls[0][2]).item() * 100:.1f}%",
                'text_attribute': f"{F.sigmoid(logits_multicls[0][3]).item() * 100:.1f}%"
            }
        }
    print(3.)
    return result


def save_to_csv(news_info, report):
    with open('src/static/frontend/llmsearch.csv', 'a', newline='') as csvfile:
        fieldnames = [
            'timestamp', 'title', 'url', 'final_verdict', 
            'confidence', 'date'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if csvfile.tell() == 0:
            writer.writeheader()
        
        # Accessing attributes instead of using dictionary-style access
        writer.writerow({
            'timestamp': datetime.now().isoformat(),
            'title': news_info['title'],
            'url': news_info['url'],
            'final_verdict': report.final_verdict,  # Accessing as attribute
            'confidence': report.confidence,  # Accessing as attribute
            'date': news_info['date']
        })



