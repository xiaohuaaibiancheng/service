class ConsensusAnalyzer {
    constructor() {
        this.wordCloudChart = echarts.init(document.getElementById('keyword-cloud'));
    }

    analyze(newsItems) {
        // 提取共同关键信息
        const corePoints = this.extractCorePoints(newsItems);
        
        // 生成关键词云
        const keywords = this.extractKeywords(newsItems);
        
        // 计算可信度
        const credibility = this.calculateCredibility(newsItems);
        
        return {
            corePoints,
            keywords,
            credibility
        };
    }

    extractCorePoints(newsItems) {
        // 使用简单的文本匹配找出多个来源都提到的信息
        const commonPhrases = this.findCommonPhrases(newsItems);
        return commonPhrases.slice(0, 5).map(phrase => ({
            text: phrase,
            sources: this.findSourcesForPhrase(phrase, newsItems)
        }));
    }

    findCommonPhrases(newsItems) {
        // 将每条新闻分成句子
        const allSentences = newsItems.flatMap(item => 
            item.content.split(/[。！？]/).filter(s => s.length > 10)
        );

        // 找出相似的句子
        const commonPhrases = [];
        for (let i = 0; i < allSentences.length; i++) {
            for (let j = i + 1; j < allSentences.length; j++) {
                const similarity = this.calculateSimilarity(
                    allSentences[i],
                    allSentences[j]
                );
                if (similarity > 0.7) {  // 相似度阈值
                    commonPhrases.push(allSentences[i]);
                }
            }
        }

        return [...new Set(commonPhrases)];
    }

    calculateSimilarity(text1, text2) {
        // 简单的词重叠计算
        const words1 = new Set(text1.split(''));
        const words2 = new Set(text2.split(''));
        const intersection = new Set([...words1].filter(x => words2.has(x)));
        return intersection.size / Math.max(words1.size, words2.size);
    }

    updateUI(result) {
        // 更新核心信息
        const corePointsContainer = document.getElementById('core-points');
        corePointsContainer.innerHTML = result.corePoints.map(point => `
            <div class="point-item">
                <i class="fas fa-check point-icon"></i>
                <div>
                    <div>${point.text}</div>
                    <small class="text-muted">
                        ${point.sources.length} 个来源报道
                    </small>
                </div>
            </div>
        `).join('');

        // 更新关键词云
        this.wordCloudChart.setOption({
            series: [{
                type: 'wordCloud',
                data: result.keywords.map(k => ({
                    name: k.word,
                    value: k.weight * 100
                })),
                textStyle: {
                    color: () => {
                        return ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'][
                            Math.floor(Math.random() * 5)
                        ];
                    }
                }
            }]
        });

        // 更新可信度指标
        const credibilityBar = document.getElementById('credibility-bar');
        const credibilityScore = document.getElementById('credibility-score');
        credibilityBar.style.width = `${result.credibility}%`;
        credibilityScore.textContent = `${result.credibility}%`;
    }
} 