// 编辑器实例
let editor;

// 添加图表实例管理
const charts = new Map();

// 初始化编辑器
function initEditor() {
    const { createEditor, createToolbar } = window.wangEditor;

    // 编辑器配置
    const editorConfig = {
        placeholder: '请输入或粘贴需要检测的新闻内容...',
        MENU_CONF: {
            uploadImage: {
                server: '/api/upload_image',
                fieldName: 'image',
                maxFileSize: 10 * 1024 * 1024,
                allowedFileTypes: ['image/*'],
                base64LimitSize: 5 * 1024 * 1024
            }
        },
        // 粘贴文本时的处理
        PASTE_FILTER_STYLE: false,
        PASTE_HTML_MAX_LENGTH: 99999,
        // 粘贴图片的处理
        pasteHandler: handleImagePaste
    };

    // 创建编辑器
    editor = createEditor({
        selector: '#editor-text',
        config: editorConfig,
        html: ''
    });

    // 创建工具栏
    const toolbar = createToolbar({
        editor,
        selector: '#editor-toolbar',
        config: {
            excludeKeys: [
                'group-video',
                'group-code',
                'insertTable'
            ]
        }
    });

    // 更新字数统计
    editor.on('change', updateWordCount);
}

// 处理图片粘贴
async function handleImagePaste(editor, event) {
    const clipboardData = event.clipboardData;
    const items = clipboardData?.items;
    
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.includes('image')) {
            const file = item.getAsFile();
            if (!file) continue;

            try {
                const imageUrl = await uploadImage(file);
                if (imageUrl) {
                    editor.insertImage(imageUrl);
                }
            } catch (error) {
                console.error('Error uploading pasted image:', error);
            }
        }
    }
}

// 上传图片
async function uploadImage(file) {
    const formData = new FormData();
    formData.append('image', file);
    
    try {
        const response = await fetch('/api/upload_image', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        if (data.errno === 0) {
            return {
                url: data.data.url,
                alt: data.data.alt,
                href: data.data.href
            };
        }
    } catch (error) {
        console.error('Error:', error);
    }
    return null;
}

// 更新字数统计
function updateWordCount() {
    const text = editor.getText();
    document.getElementById('wordCount').textContent = text.length;
}

// 开始检测
function startDetect() {
    const htmlContent = editor.getHtml();
    if (!htmlContent.trim()) {
        alert('请输入新闻内容');
        return;
    }

    showLoading();
    submitContent(htmlContent)
        .then(handleResponse)
        .catch(handleError)
        .finally(hideLoading);
}

// 提交内容
async function submitContent(content) {
    const response = await fetch('/api/submit_text_content', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ content })
    });
    return response.json();
}

// 处理响应
function handleResponse(data) {
    if (data.status === 'success' && data.data) {
        showResult(data.data);
    } else {
        throw new Error(data.message || '检测失败');
    }
}

// 显示检测结果
function showResult(data) {
    console.log('Showing result:', data);
    
    const resultPanel = document.getElementById('result-panel');
    resultPanel.style.display = 'block';
    setTimeout(() => resultPanel.classList.add('show'), 10);

    updateResultContent(data);
}

// 更新结果内容
function updateResultContent(data) {
    console.log('Received data:', data); // 查看实际返回的数据结构

    // 基本信息
    document.getElementById('news-title').textContent = data.title || '未知标题';
    document.getElementById('news-date').textContent = data.publish_time || '';
    document.getElementById('news-source').textContent = data.platform || '';

    // 可信度和真实性
    const credibilityScore = Math.round((data.credibility?.score || 0) * 100);
    document.getElementById('credibility-score').textContent = credibilityScore;
    
    const authElement = document.getElementById('authenticity');
    authElement.textContent = data.label || '未知';
    document.getElementById('verdict-badge').style.backgroundColor = 
        data.label === '真实' ? '#2ecc71' : '#e74c3c';

    // 渲染各种图表
    try {
        // 维度分析雷达图
        if (data.credibility?.dimension_scores) {
            renderDimensionChart(data.credibility.dimension_scores);
        }

        // 用户画像分析
        const userProfile = {
            verified_users: 30,  // 示例数据，实际应该从data中获取
            regular_users: 50,
            new_users: 20,
            total_users: 100,
            active_users: 80,
            influence_score: 85
        };
        renderUserProfileChart(userProfile);
        updateUserStats(userProfile);

        // 传播趋势分析
        const timelineData = [
            { date: '2025-02-15', shares: 100, comments: 50 },
            { date: '2025-02-16', shares: 200, comments: 80 },
            { date: '2025-02-17', shares: 150, comments: 60 }
        ];
        renderTimelineChart(timelineData);
    } catch (error) {
        console.error('Error rendering charts:', error);
    }
}

// 渲染维度分析雷达图
function renderDimensionChart(scores) {
    const chart = initChart('dimension-chart');
    
    const option = {
        radar: {
            indicator: [
                { name: '来源可信度', max: 100 },
                { name: '内容一致性', max: 100 },
                { name: '逻辑评判', max: 100 },
                { name: '传播置信度', max: 100 }
            ]
        },
        series: [{
            type: 'radar',
            data: [{
                value: [
                    scores.source * 100,
                    scores.content * 100,
                    scores.logic * 100,
                    scores.propagation * 100
                ],
                name: '维度得分'
            }]
        }]
    };
    
    chart.setOption(option);
}

// 修改用户画像饼图渲染函数
function renderUserProfileChart(profile) {
    const chart = initChart('user-profile-chart');
    
    const option = {
        title: {
            text: '用户类型分布',
            left: 'center'
        },
        tooltip: {
            trigger: 'item',
            formatter: '{b}: {c} ({d}%)'
        },
        legend: {
            orient: 'vertical',
            left: 'left'
        },
        series: [{
            name: '用户类型',
            type: 'pie',
            radius: ['50%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: {
                borderRadius: 10,
                borderColor: '#fff',
                borderWidth: 2
            },
            label: {
                show: true,
                formatter: '{b}: {c} ({d}%)'
            },
            emphasis: {
                label: {
                    show: true,
                    fontSize: '20',
                    fontWeight: 'bold'
                }
            },
            data: [
                { value: profile.verified_users, name: '认证用户' },
                { value: profile.regular_users, name: '普通用户' },
                { value: profile.new_users, name: '新用户' }
            ]
        }]
    };
    
    chart.setOption(option);
}

// 修改传播趋势图渲染函数
function renderTimelineChart(timeline) {
    const chart = initChart('timeline-chart');
    
    const option = {
        title: {
            text: '传播趋势分析',
            left: 'center'
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'shadow'
            }
        },
        legend: {
            data: ['转发量', '评论量'],
            top: '30px'
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: timeline.map(item => item.date),
            axisLabel: {
                rotate: 45
            }
        },
        yAxis: {
            type: 'value',
            name: '数量'
        },
        series: [
            {
                name: '转发量',
                type: 'line',
                smooth: true,
                data: timeline.map(item => item.shares),
                itemStyle: {
                    color: '#3498db'
                },
                areaStyle: {
                    opacity: 0.1
                }
            },
            {
                name: '评论量',
                type: 'line',
                smooth: true,
                data: timeline.map(item => item.comments),
                itemStyle: {
                    color: '#2ecc71'
                },
                areaStyle: {
                    opacity: 0.1
                }
            }
        ]
    };
    
    chart.setOption(option);
}

// 更新用户统计信息
function updateUserStats(profile) {
    // 检查数据是否存在
    if (!profile) {
        console.log('No user profile data available');
        return;
    }

    const statsContainer = document.getElementById('user-stats');
    statsContainer.innerHTML = `
        <div class="stat-item">
            <div class="stat-value">${profile.total_users || 0}</div>
            <div class="stat-label">总用户数</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${profile.active_users || 0}</div>
            <div class="stat-label">活跃用户</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${profile.influence_score || 0}</div>
            <div class="stat-label">影响力指数</div>
        </div>
    `;
}

// 添加图表实例管理
function initChart(containerId) {
    if (charts.has(containerId)) {
        charts.get(containerId).dispose();
    }
    const chart = echarts.init(document.getElementById(containerId));
    charts.set(containerId, chart);
    return chart;
}

// 添加数据验证
function validateData(data) {
    const required = {
        title: '未知标题',
        publish_time: '',
        platform: '',
        credibility: {
            score: 0,
            dimension_scores: {
                source: 0,
                content: 0,
                logic: 0,
                propagation: 0
            }
        },
        propagation: {
            timeline: [],
            user_profile: {
                age_dist: {},
                device_ratio: {}
            }
        }
    };
    
    return deepMerge(required, data);
}

// 清理资源
function cleanup() {
    charts.forEach(chart => chart.dispose());
    charts.clear();
}

// 窗口大小改变时重绘图表
window.addEventListener('resize', () => {
    charts.forEach(chart => chart.resize());
});

// 页面卸载时清理资源
window.addEventListener('beforeunload', cleanup);

// 处理错误
function handleError(error) {
    console.error('Error:', error);
    alert('检测失败: ' + error.message);
}

// 显示加载动画
function showLoading() {
    document.getElementById('loading-container').style.display = 'block';
}

// 隐藏加载动画
function hideLoading() {
    document.getElementById('loading-container').style.display = 'none';
}

// 隐藏结果
function hideResult() {
    const resultPanel = document.getElementById('result-panel');
    resultPanel.classList.remove('show');
    setTimeout(() => resultPanel.style.display = 'none', 300);
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', initEditor);

// 页面卸载时销毁编辑器
window.onbeforeunload = () => {
    if (editor) {
        editor.destroy();
    }
};

// 一键排版功能
function formatText() {
    const content = editor.getHtml();
    const formatted = content.replace(/\n\s*\n/g, '</p><p>')
                            .replace(/([。！？])\s*/g, '$1</p><p>');
    editor.setHtml(`<p>${formatted}</p>`);
}

// 提取关键词
function extractKeywords() {
    const content = editor.getText();
    // 使用简单的TF-IDF算法提取关键词
    const words = content.split(/\s+/);
    const frequency = {};
    words.forEach(word => {
        frequency[word] = (frequency[word] || 0) + 1;
    });
    
    // 显示关键词标签云
    showKeywordCloud(frequency);
}

// 文本翻译
function translateContent() {
    const text = editor.getText();
    const targetLang = 'en'; // 默认翻译为英文
    
    fetch(`/api/translate?text=${encodeURIComponent(text)}&target=${targetLang}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showTranslation(data.translated);
            }
        });
}

// 文本朗读
let speechSynthesis;
function readAloud() {
    const text = editor.getText();
    if ('speechSynthesis' in window) {
        speechSynthesis = new SpeechSynthesisUtterance(text);
        speechSynthesis.lang = 'zh-CN';
        window.speechSynthesis.speak(speechSynthesis);
    }
}

// 实时预览
let previewTimer;
editor.on('change', () => {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(() => {
        updatePreview();
    }, 500);
});

function updatePreview() {
    const content = editor.getHtml();
    document.getElementById('preview-container').innerHTML = content;
}

function togglePreview(device) {
    const container = document.getElementById('preview-container');
    container.className = `preview-content preview-${device}`;
}

// 添加快捷键支持
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey) {
        switch(e.key) {
            case 'b':
                e.preventDefault();
                editor.execCommand('bold');
                break;
            case 'i':
                e.preventDefault();
                editor.execCommand('italic');
                break;
            case 'u':
                e.preventDefault();
                editor.execCommand('underline');
                break;
            case 'z':
                e.preventDefault();
                editor.execCommand('undo');
                break;
            case 'y':
                e.preventDefault();
                editor.execCommand('redo');
                break;
        }
    }
});

// 添加拖放支持
editor.on('drop', (e) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFiles(files);
    }
});

function handleFiles(files) {
    Array.from(files).forEach(file => {
        if (file.type.startsWith('image/')) {
            uploadImage(file);
        } else if (file.type === 'text/plain') {
            const reader = new FileReader();
            reader.onload = (e) => {
                editor.insertText(e.target.result);
            };
            reader.readAsText(file);
        }
    });
} 