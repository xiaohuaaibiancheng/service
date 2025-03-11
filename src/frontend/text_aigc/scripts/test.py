# -*- coding: utf-8 -*-
import torch
import glob
import json
import numpy as np
import os
from transformers import AutoTokenizer, AutoModelForCausalLM
from model import load_tokenizer, load_model  # 使用你的本地模型加载代码
import sys

# 添加项目根目录到系统路径，以便导入src.config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, LOCAL_MODEL_NAME, LOCAL_MODEL_REF_PATH, LOCAL_MODEL_CACHE_DIR, USE_OPENAI_API

# 选择使用本地模型还是 OpenAI API
# USE_OPENAI_API = True  # 设置为 True 以使用 OpenAI API，否则使用本地模型
# 使用配置中的设置

if USE_OPENAI_API:
    import openai
    openai.api_key = OPENAI_API_KEY
    openai.base_url = OPENAI_BASE_URL


class ProbEstimator:
    def __init__(self, ref_path):
        self.real_crits = []
        self.fake_crits = []
        for result_file in glob.glob(os.path.join(ref_path, '*.json')):
            with open(result_file, 'r') as fin:
                res = json.load(fin)
                self.real_crits.extend(res['predictions']['real'])
                self.fake_crits.extend(res['predictions']['samples'])
        
        print(f'ProbEstimator: total {len(self.real_crits) * 2} samples.')

    def crit_to_prob(self, crit):
        """ 计算 AI 生成的概率 """
        offset = np.percentile(np.abs(np.array(self.real_crits + self.fake_crits) - crit), 10)

        cnt_real = np.sum((np.array(self.real_crits) > crit - offset) & (np.array(self.real_crits) < crit + offset))
        cnt_fake = np.sum((np.array(self.fake_crits) > crit - offset) & (np.array(self.fake_crits) < crit + offset))

        if cnt_real + cnt_fake == 0:
            return 0.5  # 避免除零错误，返回 50% 概率

        return cnt_fake / (cnt_real + cnt_fake)


def get_sampling_discrepancy_analytic(logits_ref, logits_score, labels):
    """ 计算对数概率的离散度 """
    assert logits_ref.shape[0] == 1
    assert logits_score.shape[0] == 1
    assert labels.shape[0] == 1

    labels = labels.unsqueeze(-1) if labels.ndim == logits_score.ndim - 1 else labels
    lprobs_score = torch.log_softmax(logits_score, dim=-1)
    probs_ref = torch.softmax(logits_ref, dim=-1)
    log_likelihood = lprobs_score.gather(dim=-1, index=labels).squeeze(-1)
    mean_ref = (probs_ref * lprobs_score).sum(dim=-1)
    var_ref = (probs_ref * torch.square(lprobs_score)).sum(dim=-1) - torch.square(mean_ref)
    
    discrepancy = (log_likelihood.sum(dim=-1) - mean_ref.sum(dim=-1)) / var_ref.sum(dim=-1).sqrt()
    discrepancy = discrepancy.mean()

    return discrepancy.item()


class DetectAIGC:
    """AI生成内容检测器"""
    def __init__(self, model_name=LOCAL_MODEL_NAME, ref_path=LOCAL_MODEL_REF_PATH, device="cuda", cache_dir=LOCAL_MODEL_CACHE_DIR):
        self.model_name = model_name
        self.ref_path = ref_path
        self.device = device
        self.cache_dir = cache_dir
        self.use_openai_api = USE_OPENAI_API

        if not self.use_openai_api:
            # 加载本地模型和 tokenizer
            self.tokenizer, self.model = load_tokenizer(model_name, cache_dir), load_model(model_name, cache_dir)
            self.model.to(device)
            self.model.eval()

        # 初始化概率估计器
        self.prob_estimator = ProbEstimator(self.ref_path)

    def get_log_likelihood_openai(self, text):
        """ 通过 OpenAI API 获取对数概率 """
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": text}],
            temperature=0,
            max_tokens=0,
            logprobs=True,
            top_logprobs=2
        )
        logprobs = response.choices[0].logprobs.content
        total_logprob = sum([logprob.logprob for logprob in logprobs])

        print(f'Total log likelihood (OpenAI): {total_logprob}')
        return total_logprob

    def get_log_likelihood_local(self, text):
        """ 通过本地模型计算对数概率 """
        tokenized = self.tokenizer(text, truncation=True, return_tensors="pt", padding=True, return_token_type_ids=False).to(self.device)
        labels = tokenized.input_ids[:, 1:]

        with torch.no_grad():
            logits = self.model(**tokenized).logits[:, :-1]

        # 计算对数概率
        log_likelihood = torch.log_softmax(logits, dim=-1).gather(dim=-1, index=labels.unsqueeze(-1)).squeeze(-1)
        total_logprob = log_likelihood.sum().item()

        print(f'Total log likelihood (Local): {total_logprob}')
        return total_logprob

    def predict_prob(self, text):
        """ 预测文本是 AI 生成的概率 """
        if self.use_openai_api:
            log_likelihood = self.get_log_likelihood_openai(text)
        else:
            log_likelihood = self.get_log_likelihood_local(text)

        # 归一化 log likelihood
        normalized_log_likelihood = log_likelihood / len(text) if len(text) > 0 else log_likelihood

        # 计算 crit 值
        mean = np.mean(self.prob_estimator.real_crits + self.prob_estimator.fake_crits)
        std = np.std(self.prob_estimator.real_crits + self.prob_estimator.fake_crits)

        crit = (normalized_log_likelihood - mean) / (std + 1e-6)  # 避免 std 为 0
        print(f'Crit value: {crit}')

        # 计算 AI 生成概率
        prob = self.prob_estimator.crit_to_prob(crit)
        return prob


# 使用示例
if __name__ == '__main__':
    text = """春天是美丽的，春天是温暖的，春天是充满生机的。在春天，我们看到绿草如茵，花朵绽放，鸟儿歌唱。春天让人心情愉悦，春天是一个新的开始，春天带来希望和欢乐。春天，春天，春天，永远是那么美好。

"""

    detector = DetectAIGC()

    prob = detector.predict_prob(text)
    print(f'Fast-DetectGPT 预测该文本有 {prob * 100:.0f}% 可能是 AI 生成的。')
