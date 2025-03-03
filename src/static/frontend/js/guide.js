// 检查是否是新用户
function isNewUser() {
    return !localStorage.getItem('hasSeenGuide');
}

// 首页引导
function startHomeGuide() {
    introJs().setOptions({
        steps: [
            {
                title: '欢迎使用',
                intro: '欢迎使用虚假新闻检测系统！让我们快速了解一下主要功能。'
            },
            {
                element: '.navbar-brand',
                title: '系统首页',
                intro: '点击这里随时返回首页。'
            },
            {
                element: '.detection-methods',
                title: '检测方式',
                intro: '您可以选择文本输入、URL输入或文件上传三种方式进行检测。'
            },
            {
                element: '#editor',
                title: '内容输入',
                intro: '在这里输入或粘贴需要检测的内容。'
            },
            {
                element: '.btn-primary',
                title: '开始检测',
                intro: '点击这里开始检测分析。'
            }
        ],
        nextLabel: '下一步',
        prevLabel: '上一步',
        skipLabel: '跳过',
        doneLabel: '完成',
        showProgress: true,
        showBullets: true,
        exitOnOverlayClick: false,
        exitOnEsc: false,
        disableInteraction: false
    }).start().oncomplete(function() {
        localStorage.setItem('hasSeenGuide', 'true');
    });
}

// 检测页面引导
function startDetectGuide() {
    introJs().setOptions({
        steps: [
            {
                element: '.detection-methods',
                title: '选择检测方式',
                intro: '选择合适的检测方式开始分析。'
            },
            {
                element: '#editor',
                title: '输入内容',
                intro: '输入需要检测的新闻内容。'
            },
            {
                element: '.btn-primary',
                title: '开始检测',
                intro: '点击开始检测，系统将对内容进行分析。'
            },
            {
                element: '#result',
                title: '检测结果',
                intro: '这里将显示详细的检测结果和分析。'
            }
        ],
        nextLabel: '下一步',
        prevLabel: '上一步',
        skipLabel: '跳过',
        doneLabel: '完成'
    }).start();
}

// 用户中心引导
function startUserGuide() {
    introJs().setOptions({
        steps: [
            {
                element: '.user-info',
                title: '个人信息',
                intro: '这里显示您的基本信息。'
            },
            {
                element: '.user-menu',
                title: '功能菜单',
                intro: '这里可以访问各种用户功能。'
            },
            {
                element: '.detection-history',
                title: '检测历史',
                intro: '查看您的所有检测记录。'
            }
        ],
        nextLabel: '下一步',
        prevLabel: '上一步',
        skipLabel: '跳过',
        doneLabel: '完成'
    }).start();
}

// 在页面加载时检查并启动引导
document.addEventListener('DOMContentLoaded', function() {
    // 获取当前页面类型
    const pageType = document.body.dataset.page;
    
    // 对于新用户，自动启动引导
    if (isNewUser()) {
        switch(pageType) {
            case 'home':
                startHomeGuide();
                break;
            case 'detect':
                startDetectGuide();
                break;
            case 'user':
                startUserGuide();
                break;
        }
    }
}); 