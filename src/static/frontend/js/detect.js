// 检测相关功能
function startDetect() {
    const method = document.querySelector('.btn-group button.active').dataset.method;
    let content;
    
    // 根据不同检测方式获取内容
    switch(method) {
        case 'text':
            content = editor.getHtml();
            break;
        case 'url':
            content = document.querySelector('input[type="url"]').value;
            break;
        case 'file':
            content = document.querySelector('input[type="file"]').files[0];
            break;
    }

    // 模拟检测过程
    showLoading();
    setTimeout(() => {
        // 模拟检测结果
        const mockResult = {
            id: 'test_001',
            result: '真实',
            confidence: 95.5,
            analysis: '根据内容分析,该新闻真实性较高...',
            contentScore: 85,
            sourceScore: 90,
            riskScore: 30,
            suggestions: {
                positive: [
                    '交叉验证信息来源',
                    '查看官方声明',
                    '关注权威媒体报道'
                ],
                negative: [
                    '避免直接转发',
                    '谨慎对待未经证实的信息',
                    '注意信息时效性'
                ]
            },
            resources: [
                {
                    title: '相关新闻报道',
                    url: '#',
                    type: '新闻',
                    description: '权威媒体的相关报道'
                },
                {
                    title: '官方声明',
                    url: '#',
                    type: '声明',
                    description: '相关部门的官方回应'
                }
            ]
        };
        showResult(mockResult);
    }, 1000);
}

// 处理检测请求
async function handleDetect(content, type) {
    showLoading();
    
    // 模拟检测过程
    setTimeout(() => {
        // 模拟检测结果
        const mockResult = {
            id: 'test_001',
            result: '真实',
            confidence: 95.5,
            analysis: '根据内容分析,该新闻真实性较高...',
            contentScore: 85,
            sourceScore: 90,
            riskScore: 30,
            suggestions: {
                positive: [
                    '交叉验证信息来源',
                    '查看官方声明',
                    '关注权威媒体报道'
                ],
                negative: [
                    '避免直接转发',
                    '谨慎对待未经证实的信息',
                    '注意信息时效性'
                ]
            },
            resources: [
                {
                    title: '相关新闻报道',
                    url: '#',
                    type: '新闻',
                    description: '权威媒体的相关报道'
                },
                {
                    title: '官方声明',
                    url: '#',
                    type: '声明',
                    description: '相关部门的官方回应'
                }
            ]
        };
        showResult(mockResult);
    }, 1000);
}

// 显示加载状态
function showLoading() {
    const resultDiv = document.getElementById('result');
    resultDiv.classList.remove('d-none');
    resultDiv.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">检测中...</span>
            </div>
            <p class="mt-2">正在检测中，请稍候...</p>
        </div>
    `;
}

// 显示检测结果
function showResult(result) {
    const resultDiv = document.getElementById('result');
    resultDiv.innerHTML = `
        <input type="hidden" id="detectionId" value="${result.id}">
        <div class="card">
            <div class="card-body">
                <!-- 顶部操作栏 -->
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h5 class="card-title mb-0">检测结果</h5>
                    <div class="btn-group">
                        <button class="btn btn-outline-primary" onclick="exportReport()">
                            <i class="fas fa-download me-2"></i>导出报告
                        </button>
                        <button class="btn btn-outline-success" onclick="shareResult()">
                            <i class="fas fa-share-alt me-2"></i>分享
                        </button>
                    </div>
                </div>

                <!-- 主要结果 -->
                <div class="result-content">
                    <div class="alert ${result.result === '真实' ? 'alert-success' : 'alert-danger'}">
                        <h5 class="alert-heading">
                            <i class="fas ${result.result === '真实' ? 'fa-check-circle' : 'fa-times-circle'} me-2"></i>
                            ${result.result}
                        </h5>
                        <div class="d-flex justify-content-between align-items-center">
                            <p class="mb-0">可信度：${result.confidence}%</p>
                            <span class="badge bg-info">检测ID: ${result.id}</span>
                        </div>
                    </div>

                    <!-- 详细分析 -->
                    <div class="analysis-section mt-4">
                        <h6 class="mb-3">
                            <i class="fas fa-chart-bar me-2"></i>详细分析
                        </h6>
                        <div class="card bg-light">
                            <div class="card-body">
                                <p>${result.analysis}</p>
                                <!-- 关键指标 -->
                                <div class="row mt-3">
                                    <div class="col-md-4">
                                        <div class="indicator">
                                            <small class="text-muted">内容可信度</small>
                                            <div class="progress">
                                                <div class="progress-bar" style="width: ${result.contentScore}%"></div>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="indicator">
                                            <small class="text-muted">来源可靠性</small>
                                            <div class="progress">
                                                <div class="progress-bar" style="width: ${result.sourceScore}%"></div>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="indicator">
                                            <small class="text-muted">传播风险</small>
                                            <div class="progress">
                                                <div class="progress-bar bg-warning" style="width: ${result.riskScore}%"></div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 建议措施 -->
                    <div class="suggestions-section mt-4">
                        <h6 class="mb-3">
                            <i class="fas fa-lightbulb me-2"></i>建议措施
                        </h6>
                        <div class="row">
                            <div class="col-md-6">
                                <div class="card h-100">
                                    <div class="card-body">
                                        <h6 class="card-title text-success">
                                            <i class="fas fa-check me-2"></i>可以采取的措施
                                        </h6>
                                        <ul class="list-unstyled mb-0">
                                            ${result.suggestions.positive.map(s => `
                                                <li class="mb-2"><i class="fas fa-angle-right me-2"></i>${s}</li>
                                            `).join('')}
                                        </ul>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card h-100">
                                    <div class="card-body">
                                        <h6 class="card-title text-danger">
                                            <i class="fas fa-exclamation-triangle me-2"></i>需要注意的问题
                                        </h6>
                                        <ul class="list-unstyled mb-0">
                                            ${result.suggestions.negative.map(s => `
                                                <li class="mb-2"><i class="fas fa-times me-2"></i>${s}</li>
                                            `).join('')}
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 相关资源 -->
                    <div class="resources-section mt-4">
                        <h6 class="mb-3">
                            <i class="fas fa-link me-2"></i>相关资源
                        </h6>
                        <div class="list-group">
                            ${result.resources.map(r => `
                                <a href="${r.url}" class="list-group-item list-group-item-action">
                                    <div class="d-flex w-100 justify-content-between">
                                        <h6 class="mb-1">${r.title}</h6>
                                        <small class="text-muted">${r.type}</small>
                                    </div>
                                    <p class="mb-1">${r.description}</p>
                                </a>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// 导出报告
function exportReport() {
    const detectionId = document.getElementById('detectionId').value;
    window.location.href = `/export_report/${detectionId}`;
}

// 分享结果
function shareResult() {
    // 分享功能待实现
    alert('分享功能开发中...');
} 