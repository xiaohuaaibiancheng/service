document.addEventListener('DOMContentLoaded', function() {
  // 列表页初始化
  if (window.location.pathname === '/') {
      // 加载图表
      const trendCharts = document.querySelectorAll('.trend-chart');
      trendCharts.forEach((chart) => {
          // 使用ECharts或其他图表库初始化
          // 这里可以添加图表初始化代码
      });
  }

  // 详情页初始化
  if (window.location.pathname.startsWith('/detail/')) {
      // 初始化时间轴
      const timeline = document.querySelector('.timeline');
      
      // 初始化3D图谱
      const graphContainer = document.getElementById('graph-container');
      // 使用Three.js或其他3D库初始化
      
      // 初始化用户画像雷达图
      const radarChart = document.getElementById('radar-chart');
      // 使用ECharts初始化雷达图
  }
});

// 交互功能
document.querySelectorAll('.collect-btn').forEach(button => {
  button.addEventListener('click', function() {
      // 收藏功能
      const newsId = this.closest('.news-card').dataset.newsId;
      // 发送AJAX请求
      fetch(`/api/collect/${newsId}`, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json'
          }
      });
  });
});

// 筛选功能
document.getElementById('credibility-select').addEventListener('change', function() {
  // 根据可信度筛选
  const selectedValue = this.value;
  // 调用后端API进行筛选
});

// 分类筛选
document.getElementById('category-select').addEventListener('change', function() {
  const selectedValue = this.value;
  // 调用后端API进行筛选
});

// 日期筛选
document.getElementById('start-date').addEventListener('change', function() {
  const startDate = this.value;
  const endDate = document.getElementById('end-date').value;
  // 调用后端API进行筛选
});
