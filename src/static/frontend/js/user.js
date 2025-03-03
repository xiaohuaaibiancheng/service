// 标签页切换
document.addEventListener('DOMContentLoaded', function() {
    // 标签页切换
    document.querySelectorAll('.user-menu a[data-bs-toggle="tab"]').forEach(function(element) {
        element.addEventListener('click', function(e) {
            e.preventDefault();
            // 移除所有active类
            document.querySelectorAll('.user-menu a').forEach(function(el) {
                el.classList.remove('active');
            });
            // 添加active类到当前点击的元素
            this.classList.add('active');
            
            // 显示对应的标签页
            const target = this.getAttribute('href');
            document.querySelectorAll('.tab-pane').forEach(function(pane) {
                pane.classList.remove('show', 'active');
            });
            document.querySelector(target).classList.add('show', 'active');
        });
    });

    // 个人信息表单提交
    document.getElementById('profile-form')?.addEventListener('submit', function(e) {
        e.preventDefault();
        // 这里添加表单提交逻辑
        alert('个人信息更新成功！');
    });

    // 筛选按钮点击事件
    document.querySelector('.btn-filter')?.addEventListener('click', function() {
        // 这里添加筛选逻辑
    });

    // 全部标记已读按钮点击事件
    document.querySelector('.btn-mark-all-read')?.addEventListener('click', function() {
        document.querySelectorAll('.notification-item.unread').forEach(function(item) {
            item.classList.remove('unread');
        });
    });

    // 检测记录相关功能
    // 筛选功能
    document.getElementById('filter-btn')?.addEventListener('click', function() {
        const type = document.getElementById('type-filter').value;
        const result = document.getElementById('result-filter').value;
        const date = document.getElementById('date-filter').value;
        
        // 这里添加筛选逻辑
        console.log('筛选条件:', { type, result, date });
    });

    // 查看详情
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const row = this.closest('tr');
            // 这里添加查看详情逻辑
            console.log('查看记录:', row.cells[1].textContent);
        });
    });

    // 删除记录
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            if (confirm('确定要删除这条记录吗？')) {
                const row = this.closest('tr');
                // 这里添加删除逻辑
                row.remove();
            }
        });
    });

    // 分页功能
    document.querySelectorAll('.pagination .page-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            if (!this.parentElement.classList.contains('disabled')) {
                // 这里添加分页逻辑
                console.log('切换到页码:', this.textContent);
            }
        });
    });
}); 