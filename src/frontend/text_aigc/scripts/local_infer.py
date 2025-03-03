# -*- coding: utf-8 -*-
import torch
import glob
import json
from src.frontend.text_aigc.scripts.model import load_tokenizer, load_model
import numpy as np
import os

# ProbEstimator class remains unchanged
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
        offset = np.sort(np.abs(np.array(self.real_crits + self.fake_crits) - crit))[100]
        cnt_real = np.sum((np.array(self.real_crits) > crit - offset) & (np.array(self.real_crits) < crit + offset))
        cnt_fake = np.sum((np.array(self.fake_crits) > crit - offset) & (np.array(self.fake_crits) < crit + offset))
        return cnt_fake / (cnt_real + cnt_fake)


# Function to get discrepancy value
def get_sampling_discrepancy_analytic(logits_ref, logits_score, labels):
    assert logits_ref.shape[0] == 1
    assert logits_score.shape[0] == 1
    assert labels.shape[0] == 1
    if logits_ref.size(-1) != logits_score.size(-1):
        vocab_size = min(logits_ref.size(-1), logits_score.size(-1))
        logits_ref = logits_ref[:, :, :vocab_size]
        logits_score = logits_score[:, :, :vocab_size]

    labels = labels.unsqueeze(-1) if labels.ndim == logits_score.ndim - 1 else labels
    lprobs_score = torch.log_softmax(logits_score, dim=-1)
    probs_ref = torch.softmax(logits_ref, dim=-1)
    log_likelihood = lprobs_score.gather(dim=-1, index=labels).squeeze(-1)
    mean_ref = (probs_ref * lprobs_score).sum(dim=-1)
    var_ref = (probs_ref * torch.square(lprobs_score)).sum(dim=-1) - torch.square(mean_ref)
    discrepancy = (log_likelihood.sum(dim=-1) - mean_ref.sum(dim=-1)) / var_ref.sum(dim=-1).sqrt()
    discrepancy = discrepancy.mean()
    return discrepancy.item()


# Refactored class
class DetectAIGC:
    def __init__(self, reference_model_name="gpt2-distil-chinese", scoring_model_name="gpt2-distil-chinese", dataset="xsum", ref_path="src/frontend/text_aigc/local_infer_ref", device="cuda", cache_dir="model"):
        # Initialize model and tokenizer loading during class initialization
        self.reference_model_name = reference_model_name
        self.scoring_model_name = scoring_model_name
        self.dataset = dataset
        self.ref_path = ref_path
        self.device = device
        self.cache_dir = cache_dir

        # Load models and tokenizers
        self.scoring_tokenizer = load_tokenizer(self.scoring_model_name, self.dataset, self.cache_dir)
        self.scoring_model = load_model(self.scoring_model_name, self.device, self.cache_dir)
        self.scoring_model.eval()

        if self.reference_model_name != self.scoring_model_name:
            self.reference_tokenizer = load_tokenizer(self.reference_model_name, self.dataset, self.cache_dir)
            self.reference_model = load_model(self.reference_model_name, self.device, self.cache_dir)
            self.reference_model.eval()

        # Initialize probability estimator
        self.prob_estimator = ProbEstimator(self.ref_path)

    def get_sampling_discrepancy(self, logits_ref, logits_score, labels):
        return get_sampling_discrepancy_analytic(logits_ref, logits_score, labels)

    def predict_prob(self, text):
        # Tokenize input text
        tokenized = self.scoring_tokenizer(text, truncation=True, return_tensors="pt", padding=True, return_token_type_ids=False).to(self.device)
        labels = tokenized.input_ids[:, 1:]

        # Calculate logits
        with torch.no_grad():
            logits_score = self.scoring_model(**tokenized).logits[:, :-1]
            if self.reference_model_name == self.scoring_model_name:
                logits_ref = logits_score
            else:
                tokenized = self.reference_tokenizer(text, truncation=True, return_tensors="pt", padding=True, return_token_type_ids=False).to(self.device)
                assert torch.all(tokenized.input_ids[:, 1:] == labels), "Tokenizer is mismatch."
                logits_ref = self.reference_model(**tokenized).logits[:, :-1]

            # Get sampling discrepancy
            crit = self.get_sampling_discrepancy(logits_ref, logits_score, labels)

        # Estimate the probability of machine-generated text
        prob = self.prob_estimator.crit_to_prob(crit)

        return prob


# Example usage of the class
if __name__ == '__main__':
    text = """
  　从小到现在，十几年的时间就一直生活在南方的我，从未感受过雪花纷飞、朔风凛冽的壮观，从未见过白雪皑皑，万物无息的银色世界，更从未体验过用通红的小手堆雪人、打雪站的乐趣，自然也难以理解"忽如一夜春风来，千树万树犁花开"的忽然与神奇。所以，我只能说说我所熟悉的南方的冬天。体验南方的冬天实在是一件难得的乐事。

今年的冬天来得有点晚，以至当它真的来临的时候，让人有些措手不及。前几天，还是阳光暖暖、金风飒爽的秋日，而昨天气温聚降，冷风肆掠，似乎告诉我们：冬天，真的来了。

早晨起来，睁开惺忪的睡眼，发现天还没亮，而指针已指向了'6"。手一伸出被窝，马上就冷得缩回去了，起床的决心不免有些动摇。毫不轻易走出公寓，抬眼望去，三两个行人和老屋都沉浸在这厚厚的浓雾中，如沉睡一般，还未醒来。星星点点的光晕在晨雾中酝酿，隐约可见，这该算是冬的一点柔和吧！然而，空气实在干燥得很，深呼吸一口，让人觉得不是滋味。薄薄的一层保湿霜，显得如此微不足道。一阵风刮来，卷起一地的落叶，在风中旋着，飘着，我不由得裹紧了衣领，向餐厅走去。

一路上，看到落叶仍然保留着夏的颜色，却毫无生气，耷拉着树枝，在风中瑟瑟发抖。小鸟不得不夹紧翅膀，慵懒地躲在鸟窝中，不想离开。草地上闪烁着一颗颗晶莹透亮的露珠，压弯了小草的腰，似乎在和小草较着劲儿呢。轻轻一碰，露珠便顺着草叶快速地滑下，滴入肥沃的泥土，再空中留下一段美丽的弧线。

太阳懒洋洋地升起来了，吝啬地给予大地几缕微弱的日光。操场上的人也多了，在尚未褪去的浓雾里急走穿行，步履匆匆。每个人都穿的不多，但已足以抵御冰冷的寒风。校园外的田地里，辛勤的农民挑着水，再地里摆弄冬日脆弱的绿色。

冬日，象慈爱的老人，慵懒而又快乐；冬日，象一壶飘香四溢的茶，需要你细细的咂摸。

体验一个冬天，体验一程旅途，体验一段生命。


"""

    # Initialize the DetectAIGC class
    detector = DetectAIGC()

    # Use the class to predict probability of machine-generated text
    prob = detector.predict_prob(text)
    print(f'Fast-DetectGPT criterion suggests that the text has a {prob * 100:.0f}% probability of being machine-generated.')
