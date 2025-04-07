import re
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel, pipeline
from torch.utils.data import Dataset, DataLoader
import logging
from typing import Dict, List, Any, Tuple, Optional
import jieba
import os
import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import time
from functools import lru_cache
import concurrent.futures
from pathlib import Path
import traceback

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全局变量，定义为类变量以便更好地管理
class Constants:
    # 停用词文件路径
    STOPWORDS_PATH = r"src\static\frontend\chinese.txt"
    
    # 停用词集合
    STOPWORDS = set()
    
    # 虚假新闻的特征词汇（这些词在虚假新闻中出现频率较高）
    FAKE_NEWS_KEYWORDS = {
        '震惊', '惊爆', '曝光', '揭秘', '惊人', '骇人听闻', '天价', '内幕',
        '秘密', '绝密', '独家', '重磅', '突发', '紧急', '最新消息', '不看后悔',
        '转发', '扩散', '紧急通知', '不得不看', '必看', '奇迹', '神奇', '惊喜',
        '爆料', '惊天', '不可思议', '震撼', '狂热', '疯狂', '极端', '绝对',
        '万万没想到', '不可错过', '不看会后悔', '百分百', '无法相信', '网传',
        '秒杀', '爆红', '刷屏', '引爆', '颠覆', '逆天', '史诗级', '前所未有'
    }

    # 可信新闻的特征词汇
    CREDIBLE_NEWS_KEYWORDS = {
        '报道', '消息', '通讯', '采访', '调查', '研究', '分析', '数据',
        '专家', '学者', '官方', '权威', '证实', '证明', '表示', '称',
        '透露', '公布', '发布', '宣布', '强调', '指出', '认为', '观点'
    }
    
    # 模型相关常量
    MODEL_PATH = 'model/new_model'
    TOKENIZER_PATH = 'model/tokenizer'
    
    @classmethod
    def load_stopwords(cls):
        """加载停用词"""
        try:
            path = Path(cls.STOPWORDS_PATH)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        cls.STOPWORDS.add(line.strip())
                logger.info(f"已加载 {len(cls.STOPWORDS)} 个停用词")
            else:
                logger.warning(f"停用词文件未找到: {cls.STOPWORDS_PATH}")
        except Exception as e:
            logger.warning(f"加载停用词出错: {str(e)}")

# 初始化常量
Constants.load_stopwords()

# 情感分析模型 - 使用缓存加载
@lru_cache(maxsize=1)
def get_sentiment_analyzer():
    """获取情感分析器（带缓存）"""
    logger.info("加载情感分析模型...")
    return pipeline("sentiment-analysis", model="nghuyong/ernie-3.0-base-zh")

# 全局情感分析器实例
sentiment_analyzer = None

class NewsDataset(Dataset):
    """新闻数据集类"""
    def __init__(self, titles, contents, labels=None, tokenizer=None, max_length=512):
        self.titles = titles
        self.contents = contents
        self.labels = labels
        self.tokenizer = tokenizer if tokenizer else AutoTokenizer.from_pretrained(
            Constants.TOKENIZER_PATH,
            local_files_only=True
        )
        self.max_length = max_length

    def __len__(self):
        return len(self.titles)

    def __getitem__(self, idx):
        title = str(self.titles[idx])
        content = str(self.contents[idx])
        
        # 截取内容以避免过长
        if len(content) > 1000:
            content = content[:1000]
            
        text = title + "[SEP]" + content

        encoding = self.tokenizer.encode_plus(
            text,
            add_special_tokens=True,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_attention_mask=True,
            return_tensors='pt'
        )

        item = {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten()
        }

        if self.labels is not None:
            item['labels'] = torch.tensor(self.labels[idx], dtype=torch.long)

        return item

class NewsClassifier(nn.Module):
    """改进的新闻分类模型"""
    def __init__(self, pretrained_model=Constants.MODEL_PATH, num_classes=2, dropout_rate=0.2):
        super(NewsClassifier, self).__init__()
        self.bert = AutoModel.from_pretrained(pretrained_model)
        self.dropout = nn.Dropout(dropout_rate)
        
        # 增加模型复杂度
        hidden_size = self.bert.config.hidden_size
        self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
        self.fc2 = nn.Linear(hidden_size // 2, num_classes)
        self.relu = nn.ReLU()
        self.layer_norm = nn.LayerNorm(hidden_size // 2)
        
    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        
        # 使用[CLS]标记的输出作为整个序列的表示
        pooled_output = outputs.last_hidden_state[:, 0, :]
        
        # 添加更复杂的分类头
        x = self.dropout(pooled_output)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.layer_norm(x)
        x = self.dropout(x)
        logits = self.fc2(x)
        
        return logits

class FakeNewsDetector:
    """改进的虚假新闻检测器类"""
    
    # 定义特征阈值和分析理由 - 作为类属性以便在不同方法中重用
    FEATURE_THRESHOLDS = {
        "标题夸张度": {"threshold": 0.6, "condition": "gt", "message": "标题夸张度较高"},
        "情感_sentiment_volatility": {"threshold": 0.4, "condition": "gt", "message": "情感波动较大"},
        "标题内容一致性": {"threshold": 0.3, "condition": "lt", "message": "标题与内容相关性较低"},
        "内容可信度": {"threshold": 0.4, "condition": "lt", "message": "内容可信度较低"},
        "语言_unique_word_ratio": {"threshold": 0.3, "condition": "lt", "message": "文本词汇多样性不足"},
        "语义复杂度": {"threshold": 0.6, "condition": "lt", "message": "语义结构简单"}
    }

    def __init__(self, model_path=Constants.MODEL_PATH):
        """初始化检测器"""
        logger.info("初始化虚假新闻检测器")
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"使用设备: {self.device}")
        
        # 延迟加载模型和分词器
        self._tokenizer = None
        self._model = None
        self._tfidf_vectorizer = None
        self.model_path = model_path
        
        # 初始化TF-IDF向量化器
        self._init_tfidf_vectorizer()
        
        # 创建线程池
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

    def __del__(self):
        """析构函数，确保资源释放"""
        try:
            if hasattr(self, 'executor') and self.executor:
                self.executor.shutdown(wait=False)
        except Exception as e:
            logger.error(f"关闭线程池时出错: {str(e)}")

    @property
    def tokenizer(self):
        """懒加载分词器"""
        if self._tokenizer is None:
            logger.info("加载分词器...")
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    Constants.TOKENIZER_PATH,
                    local_files_only=True
                )
                logger.info("分词器加载成功")
            except Exception as e:
                logger.error(f"加载分词器失败: {str(e)}")
                raise
        return self._tokenizer
    
    @property
    def model(self):
        """懒加载模型"""
        if self._model is None:
            logger.info("加载模型...")
            try:
                # 使用transformers库直接加载预训练模型
                bert_model = AutoModel.from_pretrained(self.model_path)
                
                # 创建NewsClassifier实例并设置bert层
                self._model = NewsClassifier(pretrained_model=self.model_path)
                self._model.bert = bert_model
                
                # 将模型移动到正确的设备上并设置为评估模式
                self._model.to(self.device)
                self._model.eval()
                
                logger.info("成功加载预训练模型")
            except Exception as e:
                logger.error(f"加载预训练模型失败: {str(e)}", exc_info=True)
                # 如果加载失败，尝试使用默认初始化
                try:
                    self._model = NewsClassifier()
                    self._model.to(self.device)
                    self._model.eval()
                    logger.warning("使用默认初始化的模型")
                except Exception as e2:
                    logger.error(f"默认初始化模型也失败: {str(e2)}", exc_info=True)
                    raise
        return self._model
    
    def _init_tfidf_vectorizer(self):
        """初始化TF-IDF向量化器"""
        self._tfidf_vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words=Constants.STOPWORDS,
            tokenizer=jieba.lcut
        )

    @staticmethod
    def preprocess_text(text: str) -> List[str]:
        """文本预处理"""
        # 移除HTML标签
        text = re.sub(r'<.*?>', '', text)
        # 移除URL
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        # 移除标点符号
        text = re.sub(r'[^\w\s]', '', text)
        # 分词
        words = jieba.lcut(text)
        # 移除停用词和单字词
        words = [word for word in words if word not in Constants.STOPWORDS and len(word) > 1]
        return words

    @lru_cache(maxsize=100)
    def predict(self, title: str, content: str) -> Dict[str, float]:
        """使用模型进行预测（带缓存）"""
        # 截取内容以避免过长
        if len(content) > 1000:
            content = content[:1000]
            
        dataset = NewsDataset([title], [content], tokenizer=self.tokenizer)
        data_loader = DataLoader(dataset, batch_size=1)

        # 将计时逻辑移到这里，只记录实际预测的时间
        start_time = time.time()
        with torch.no_grad():
            for batch in data_loader:
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                outputs = self.model(input_ids, attention_mask)
                probabilities = torch.softmax(outputs, dim=1)
                real_prob = probabilities[0][0].item()
                fake_prob = probabilities[0][1].item()
        prediction_time = time.time() - start_time

        logger.info(f"模型预测耗时: {prediction_time:.2f}秒")
        
        return {
            'real_probability': real_prob,
            'fake_probability': fake_prob,
            'prediction_time': prediction_time  # 添加预测时间到返回结果
        }

    @lru_cache(maxsize=50)
    def calculate_title_exaggeration(self, title: str) -> float:
        """计算标题夸张度（带缓存）"""
        title_words = jieba.lcut(title)
        
        # 计算虚假新闻关键词比例
        fake_keyword_count = sum(1 for word in title_words if word in Constants.FAKE_NEWS_KEYWORDS)
        fake_keyword_ratio = fake_keyword_count / (len(title_words) + 1)
        
        # 计算可信新闻关键词比例
        credible_keyword_count = sum(1 for word in title_words if word in Constants.CREDIBLE_NEWS_KEYWORDS)
        credible_keyword_ratio = credible_keyword_count / (len(title_words) + 1)
        
        # 标题长度因子 - 过长的标题可能是为了吸引眼球
        length_factor = min(len(title) / 50, 1.0)
        
        # 使用情感分析模型评估标题情感
        global sentiment_analyzer
        if sentiment_analyzer is None:
            sentiment_analyzer = get_sentiment_analyzer()
            
        try:
            sentiment_result = sentiment_analyzer(title)[0]
            sentiment_score = 0
            if sentiment_result['label'] == 'POSITIVE':
                sentiment_score = sentiment_result['score']
            elif sentiment_result['label'] == 'NEGATIVE':
                sentiment_score = -sentiment_result['score']
        except Exception as e:
            logger.warning(f"情感分析失败: {str(e)}")
            sentiment_score = 0

        # 综合计算标题夸张度 - 考虑正面关键词的抵消作用
        exaggeration_score = min(
            fake_keyword_ratio * 3 + abs(sentiment_score) * 0.5 + length_factor * 0.3 - credible_keyword_ratio * 2, 
            1.0
        )
        return max(0.0, exaggeration_score)

    @lru_cache(maxsize=50)
    def calculate_content_credibility(self, content: str) -> float:
        """计算内容可信度（带缓存）"""
        content_words = jieba.lcut(content)
        
        # 计算可信度指标
        fake_keyword_count = sum(1 for word in content_words if word in Constants.FAKE_NEWS_KEYWORDS)
        credible_keyword_count = sum(1 for word in content_words if word in Constants.CREDIBLE_NEWS_KEYWORDS)
        
        # 内容长度 - 过短的内容可能缺乏详细信息
        content_length = len(content)
        length_factor = min(content_length / 500, 1.0)
        
        # 句子数量 - 更多的句子可能表示更详细的信息
        sentences = re.split(r'[。！？!?.]', content)
        sentence_count = len([s for s in sentences if len(s.strip()) > 0])
        sentence_factor = min(sentence_count / 10, 1.0)
        
        # 计算可信度得分
        if len(content_words) == 0:
            return 0.5
            
        fake_ratio = fake_keyword_count / len(content_words)
        credible_ratio = credible_keyword_count / len(content_words)
        
        credibility_score = min(
            0.5 + credible_ratio * 2 - fake_ratio * 3 + length_factor * 0.2 + sentence_factor * 0.3,
            1.0
        )
        
        return max(0.0, credibility_score)

    def calculate_sentiment_features(self, content: str) -> Dict[str, float]:
        """计算情感特征"""
        # 分词并移除停用词
        content_words = jieba.lcut(content)
        content_words = [word for word in content_words if word not in Constants.STOPWORDS]
        
        if not content_words:
            return {
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
                "neutral_ratio": 1.0,
                "sentiment_intensity": 0.0,
                "sentiment_volatility": 0.0
            }

        # 使用情感分析模型评估情感
        global sentiment_analyzer
        if sentiment_analyzer is None:
            sentiment_analyzer = get_sentiment_analyzer()
            
        # 将内容分成多个段落进行分析，避免过长
        chunks = self._split_content_into_chunks(content_words, chunk_size=20)
        sentiment_scores = []
        
        try:
            # 批量处理多个段落以提高性能
            chunk_texts = ["".join(chunk) for chunk in chunks if chunk]
            
            if not chunk_texts:
                return {
                    "positive_ratio": 0.0,
                    "negative_ratio": 0.0,
                    "neutral_ratio": 1.0,
                    "sentiment_intensity": 0.0,
                    "sentiment_volatility": 0.0
                }
                
            # 批量处理每个文本块
            batch_size = 5  # 每次处理5个文本块
            for i in range(0, len(chunk_texts), batch_size):
                batch = chunk_texts[i:i+batch_size]
                results = sentiment_analyzer(batch)
                
                for result in results:
                    score = result['score']
                    if result['label'] == 'NEGATIVE':
                        score = -score
                    sentiment_scores.append(score)
        except Exception as e:
            logger.warning(f"情感分析失败: {str(e)}")
            return {
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
                "neutral_ratio": 1.0,
                "sentiment_intensity": 0.0,
                "sentiment_volatility": 0.0
            }
        
        if not sentiment_scores:
            return {
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
                "neutral_ratio": 1.0,
                "sentiment_intensity": 0.0,
                "sentiment_volatility": 0.0
            }
            
        # 计算情感分布
        positive_scores = [s for s in sentiment_scores if s > 0.2]
        negative_scores = [s for s in sentiment_scores if s < -0.2]
        neutral_scores = [s for s in sentiment_scores if -0.2 <= s <= 0.2]
        
        total_chunks = len(sentiment_scores)
        positive_ratio = len(positive_scores) / total_chunks
        negative_ratio = len(negative_scores) / total_chunks
        neutral_ratio = len(neutral_scores) / total_chunks
        
        # 计算情感强度 - 平均绝对值
        sentiment_intensity = sum(abs(s) for s in sentiment_scores) / total_chunks
        
        # 计算情感波动性 - 标准差
        if len(sentiment_scores) > 1:
            sentiment_volatility = np.std(sentiment_scores)
        else:
            sentiment_volatility = 0.0

        return {
            "positive_ratio": positive_ratio,
            "negative_ratio": negative_ratio,
            "neutral_ratio": neutral_ratio,
            "sentiment_intensity": sentiment_intensity,
            "sentiment_volatility": sentiment_volatility
        }
        
    @staticmethod
    def _split_content_into_chunks(words: List[str], chunk_size: int = 20) -> List[List[str]]:
        """将内容分割成多个块"""
        return [words[i:i+chunk_size] for i in range(0, len(words), chunk_size)]

    @lru_cache(maxsize=50)
    def calculate_linguistic_complexity(self, text: str) -> Dict[str, float]:
        """计算语言复杂度特征（带缓存）"""
        words = jieba.lcut(text)
        if not words:
            return {
                "avg_word_length": 0.0,
                "unique_word_ratio": 0.0,
                "sentence_complexity": 0.0
            }
            
        # 平均词长
        avg_word_length = sum(len(word) for word in words) / len(words)
        
        # 词汇多样性
        unique_words = set(words)
        unique_word_ratio = len(unique_words) / len(words)
        
        # 句子复杂度 - 基于句子长度和标点符号数量
        sentences = re.split(r'[。！？!?.]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            sentence_complexity = 0.0
        else:
            avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)
            punctuation_count = len(re.findall(r'[，,；;：:\'""]', text))  
            sentence_complexity = (avg_sentence_length / 50) + (punctuation_count / (len(text) + 1))
            sentence_complexity = min(sentence_complexity, 1.0)
        
        return {
            "avg_word_length": avg_word_length,
            "unique_word_ratio": unique_word_ratio,
            "sentence_complexity": sentence_complexity
        }

    def extract_features(self, title: str, content: str) -> Dict[str, float]:
        """使用并行处理提取文本特征"""
        features = {}
        
        # 使用线程池并行提取特征
        future_exaggeration = self.executor.submit(self.calculate_title_exaggeration, title)
        future_credibility = self.executor.submit(self.calculate_content_credibility, content)
        future_sentiment = self.executor.submit(self.calculate_sentiment_features, content)
        future_linguistic = self.executor.submit(self.calculate_linguistic_complexity, content)
        
        # 提取标题夸张度
        features["标题夸张度"] = future_exaggeration.result()
        
        # 提取内容可信度
        features["内容可信度"] = future_credibility.result()

        # 提取情感特征
        sentiment_features = future_sentiment.result()
        for key, value in sentiment_features.items():
            features[f"情感_{key}"] = value

        # 提取语言复杂度特征
        linguistic_features = future_linguistic.result()
        for key, value in linguistic_features.items():
            features[f"语言_{key}"] = value
            
        # 标题与内容的一致性 - 这个很快，不需要并行
        title_words = set(jieba.lcut(title))
        content_words = set(jieba.lcut(content[:200]))  # 只检查内容的前一部分
        if title_words:
            title_content_overlap = len(title_words.intersection(content_words)) / len(title_words)
            features["标题内容一致性"] = title_content_overlap
        else:
            features["标题内容一致性"] = 0.0

        # 使用ERNIE提取语义特征
        try:
            encoded = self.tokenizer.encode_plus(
                title + "[SEP]" + content[:500],  # 只使用内容的前一部分
                max_length=512,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            )

            with torch.no_grad():
                outputs = self.model.bert(
                    input_ids=encoded['input_ids'].to(self.device),
                    attention_mask=encoded['attention_mask'].to(self.device)
                )
                embeddings = outputs.last_hidden_state.mean(dim=1)
                features["语义复杂度"] = float(torch.norm(embeddings).cpu())
        except Exception as e:
            logger.warning(f"提取语义特征失败: {str(e)}")
            features["语义复杂度"] = 0.5

        return features

    def classify(self, title: str, content: str) -> Dict[str, Any]:
        """对新闻进行分类"""
        start_time = time.time()
        
        try:
            # 并行处理模型预测和特征提取
            future_predictions = self.executor.submit(self.predict, title, content)
            future_features = self.executor.submit(self.extract_features, title, content)
            
            # 获取模型预测结果
            predictions = future_predictions.result()
            
            # 提取特征
            features = future_features.result()

            real_probability = predictions['real_probability']
            fake_probability = predictions['fake_probability']
            prediction_time = predictions['prediction_time']  # 获取预测时间
            
            # 结合特征调整预测结果
            adjusted_real_prob = real_probability
            
            # 如果标题夸张度高，降低真实概率
            if features["标题夸张度"] > 0.7:
                adjusted_real_prob *= (1 - features["标题夸张度"] * 0.3)
                
            # 如果内容可信度高，提高真实概率
            if "内容可信度" in features and features["内容可信度"] > 0.7:
                adjusted_real_prob = min(adjusted_real_prob * (1 + features["内容可信度"] * 0.2), 1.0)
                
            # 如果情感波动性高，降低真实概率
            if "情感_sentiment_volatility" in features and features["情感_sentiment_volatility"] > 0.5:
                adjusted_real_prob *= (1 - features["情感_sentiment_volatility"] * 0.1)
                
            # 确保概率在[0,1]范围内
            adjusted_real_prob = max(0.0, min(1.0, adjusted_real_prob))
            adjusted_fake_prob = 1.0 - adjusted_real_prob

            # 生成结论
            if adjusted_real_prob > 0.7:
                conclusion = "经过深度学习模型分析，该新闻内容具有较高的真实性。"
                sentiment = "可信度高"
                credibility_level = "高"
            elif adjusted_real_prob > 0.5:
                conclusion = "经过深度学习模型分析，该新闻内容可能是真实的，但建议进一步核实。"
                sentiment = "可信度中等"
                credibility_level = "中"
            else:
                conclusion = "经过深度学习模型分析，该新闻内容可能包含虚假信息，建议进一步核实。"
                sentiment = "可信度低"
                credibility_level = "低"
                
            # 添加具体的分析理由
            reasons = []
            for feature_name, config in self.FEATURE_THRESHOLDS.items():
                if feature_name in features:
                    value = features[feature_name]
                    if (config["condition"] == "gt" and value > config["threshold"]) or \
                       (config["condition"] == "lt" and value < config["threshold"]):
                        reasons.append(f"{config['message']}（{value:.2f}）")
            
            # 如果存在分析理由，添加到结论中
            if reasons:
                conclusion += " 主要原因：" + "，".join(reasons) + "。"

            total_time = time.time() - start_time
            logger.info(f"完成分类，总耗时: {total_time:.2f}秒，预测耗时: {prediction_time:.2f}秒")
            
            return {
                "real_probability": float(real_probability),
                "fake_probability": float(fake_probability),
                "adjusted_real_probability": float(adjusted_real_prob),
                "adjusted_fake_probability": float(adjusted_fake_prob),
                "conclusion": conclusion,
                "sentiment": sentiment,
                "credibility_level": credibility_level,
                "credibility_score": float(adjusted_real_prob * 10),
                "features": features,
                "prediction_time": float(prediction_time),
                "total_processing_time": float(total_time)
            }
        except Exception as e:
            logger.error(f"分类过程出错: {str(e)}")
            logger.error(traceback.format_exc())
            return self._create_error_response(str(e))
            
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "error": f"处理请求时出错: {error_message}",
            "real_probability": 0.5,
            "fake_probability": 0.5,
            "conclusion": "系统无法完成分析，请稍后再试。",
            "features": {},
            "credibility_level": "未知",
            "prediction_time": 0.0,
            "total_processing_time": 0.0
        }

# 使用单例模式管理检测器实例
class DetectorSingleton:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = FakeNewsDetector()
        return cls._instance
        
    @classmethod
    def reset_instance(cls):
        """重置实例（用于测试或重新初始化）"""
        if cls._instance:
            del cls._instance
        cls._instance = None

def detect_fake_news(title: str, content: str) -> Dict[str, Any]:
    """检测新闻真伪"""
    try:
        detector = DetectorSingleton.get_instance()
        result = detector.classify(title, content)
        return result
    except Exception as e:
        logger.error(f"虚假新闻检测出错: {str(e)}", exc_info=True)
        return {
            "error": f"处理请求时出错: {str(e)}",
            "real_probability": 0.5,
            "fake_probability": 0.5,
            "conclusion": "系统无法完成分析，请稍后再试。",
            "features": {},
            "credibility_level": "未知",
            "prediction_time": 0.0,
            "total_processing_time": 0.0
        }
    
def detect_fake_news_segmented(title: str, content: str, segment_size: int = 500) -> Dict[str, Any]:
    """对长文本进行分段分析
    
    Args:
        title: 新闻标题
        content: 新闻内容
        segment_size: 每段文本的长度（字符数）
        
    Returns:
        包含分段分析结果的字典
    """
    try:
        # 获取检测器实例
        detector = DetectorSingleton.get_instance()
        
        # 整体分析结果
        overall_result = detector.classify(title, content)
        
        # 如果内容较短，直接返回整体结果
        if len(content) <= segment_size:
            return {
                "overall_result": overall_result,
                "segments": [
                    {
                        "segment_id": "segment_1",
                        "content": content,
                        "analysis": overall_result,
                        "start_pos": 0,
                        "end_pos": len(content)
                    }
                ]
            }
        
        # 分段处理
        segments = []
        total_real_prob = 0
        total_fake_prob = 0
        
        # 将内容按句子分割
        sentences = re.split(r'([。！？!?.])', content)
        # 重新组合句子和标点
        sentences = [''.join(i) for i in zip(sentences[0::2], sentences[1::2] + [''])]
        
        current_segment = ""
        segment_id = 1
        start_pos = 0
        
        for sentence in sentences:
            # 如果当前段加上这个句子超过了segment_size，先分析当前段
            if len(current_segment) + len(sentence) > segment_size and len(current_segment) > 0:
                # 分析当前段
                segment_title = f"{title} (片段{segment_id})"
                analysis = detector.classify(segment_title, current_segment)
                
                # 添加到分段结果
                segments.append({
                    "segment_id": f"segment_{segment_id}",
                    "content": current_segment,
                    "analysis": analysis,
                    "start_pos": start_pos,
                    "end_pos": start_pos + len(current_segment)
                })
                
                # 累加概率
                total_real_prob += analysis["adjusted_real_probability"]
                total_fake_prob += analysis["adjusted_fake_probability"]
                
                # 重置当前段
                start_pos += len(current_segment)
                current_segment = sentence
                segment_id += 1
            else:
                # 将句子添加到当前段
                current_segment += sentence
        
        # 处理最后一段
        if current_segment:
            segment_title = f"{title} (片段{segment_id})"
            analysis = detector.classify(segment_title, current_segment)
            
            segments.append({
                "segment_id": f"segment_{segment_id}",
                "content": current_segment,
                "analysis": analysis,
                "start_pos": start_pos,
                "end_pos": start_pos + len(current_segment)
            })
            
            total_real_prob += analysis["adjusted_real_probability"]
            total_fake_prob += analysis["adjusted_fake_probability"]
        
        # 计算平均概率
        num_segments = len(segments)
        avg_real_prob = total_real_prob / num_segments if num_segments > 0 else 0.5
        avg_fake_prob = total_fake_prob / num_segments if num_segments > 0 else 0.5
        
        # 确保概率在[0,1]范围内
        avg_real_prob = max(0.0, min(1.0, avg_real_prob))
        avg_fake_prob = max(0.0, min(1.0, avg_fake_prob))
        
        # 生成结论
        if avg_real_prob > 0.7:
            conclusion = "经过深度学习模型分析，该新闻整体内容具有较高的真实性。"
            credibility_level = "高"
        elif avg_real_prob > 0.5:
            conclusion = "经过深度学习模型分析，该新闻整体内容可能是真实的，但建议进一步核实。"
            credibility_level = "中"
        else:
            conclusion = "经过深度学习模型分析，该新闻整体内容可能包含虚假信息，建议进一步核实。"
            credibility_level = "低"
        
        # 分析常见问题并加入到结论中
        common_issues = []
        
        # 计算各段落中的特征平均值，用于整体分析
        avg_features = {}
        feature_counts = {}
        
        # 收集所有段落的特征
        for segment in segments:
            segment_features = segment["analysis"].get("features", {})
            for feature_name, value in segment_features.items():
                if feature_name not in avg_features:
                    avg_features[feature_name] = 0
                    feature_counts[feature_name] = 0
                avg_features[feature_name] += value
                feature_counts[feature_name] += 1
        
        # 计算平均值
        for feature_name in avg_features:
            if feature_counts[feature_name] > 0:
                avg_features[feature_name] /= feature_counts[feature_name]
        
        # 获取检测器实例以访问阈值配置
        detector_instance = DetectorSingleton.get_instance()
        
        # 基于平均特征值生成分析理由
        reasons = []
        for feature_name, config in detector_instance.FEATURE_THRESHOLDS.items():
            if feature_name in avg_features:
                value = avg_features[feature_name]
                if (config["condition"] == "gt" and value > config["threshold"]) or \
                   (config["condition"] == "lt" and value < config["threshold"]):
                    reasons.append(f"{config['message']}（{value:.2f}）")
        
        # 添加段落分析结果
        if num_segments > 1:
            suspicious_count = len([s for s in segments if s["analysis"]["adjusted_real_probability"] < 0.5])
            if suspicious_count > 0:
                suspicious_ratio = suspicious_count / num_segments
                if suspicious_ratio > 0.5:
                    reasons.append(f"超过一半的段落（{suspicious_count}/{num_segments}）可信度较低")
                elif suspicious_count > 0:
                    reasons.append(f"存在{suspicious_count}个可信度较低的段落")
        
        # 如果有分析理由，添加到结论中
        if reasons:
            conclusion += " 主要分析理由：" + "，".join(reasons) + "。"
        
        # 找出最可疑的段落
        suspicious_segments = []
        for segment in segments:
            if segment["analysis"]["adjusted_real_probability"] < 0.5:
                suspicious_segments.append({
                    "segment_id": segment["segment_id"],
                    "content": segment["content"][:50] + "...",  # 只显示片段开头
                    "fake_probability": segment["analysis"]["adjusted_fake_probability"]
                })
        
        suspicious_segments.sort(key=lambda x: x["fake_probability"], reverse=True)
        
        # 如果有可疑段落，将其添加到结论中
        if suspicious_segments:
            suspicious_text = "\n".join([
                f"- 段落{i+1}（ID: {s['segment_id']}）: {s['content']} (虚假概率: {s['fake_probability']:.2f})"
                for i, s in enumerate(suspicious_segments[:3])  # 只显示前3个最可疑的段落
            ])
            conclusion += f"\n\n以下段落可能包含虚假信息，建议重点核实：\n{suspicious_text}"
        
        # 构建最终结果
        result = {
            "overall_result": {
                "real_probability": float(avg_real_prob),
                "fake_probability": float(avg_fake_prob),
                "conclusion": conclusion,
                "credibility_level": credibility_level,
                "credibility_score": float(avg_real_prob * 10),
                "total_segments": num_segments,
                "suspicious_segments": suspicious_segments[:3] if suspicious_segments else []
            },
            "segments": segments
        }
        
        return result
        
    except Exception as e:
        logger.error(f"分段虚假新闻检测出错: {str(e)}", exc_info=True)
        return {
            "error": f"处理请求时出错: {str(e)}",
            "overall_result": {
                "real_probability": 0.5,
                "fake_probability": 0.5,
                "conclusion": "系统无法完成分析，请稍后再试。",
                "credibility_level": "未知"
            },
            "segments": []
        }
    
if __name__ == "__main__":
    title = "震惊！某地发现天价内幕，不看后悔！"
    content = "近日，某地发生了一件令人震惊的事件，涉及天价内幕，引发了广泛关注。"

    result = detect_fake_news(title, content)
    print(json.dumps(result, indent=4, ensure_ascii=False))
