// 生成动态新闻卡片
function createNewsCards() {
  const newsFlow = document.querySelector('.news-flow');
  if (!newsFlow) {
    console.log('新闻流容器不存在，跳过新闻卡片创建');
    return; // 如果元素不存在，提前退出函数
  }

  // 更丰富的新闻数据结构
  const newsItems = [
    {
      title: '研究证实：新型疫苗对变异毒株有效性达95%，多国临床试验验证',
      date: '2023-12-15',
      source: '健康时报',
      status: 'true',  // true, false, pending
      statusText: '可信'
    },
    {
      title: '突发！知名企业CEO宣布辞职，内部信息称因重大财务造假被调查',
      date: '2023-12-13',
      source: '经济观察家',
      status: 'false',
      statusText: '虚假'
    },
    {
      title: '最新报道：某国或将推出全球首个量子计算商用芯片',
      date: '2023-12-12',
      source: '科技前沿',
      status: 'pending',
      statusText: '待验证'
    },
    {
      title: '气候变化报告：全球变暖致极端天气事件增加30%',
      date: '2023-12-10',
      source: '环球科学',
      status: 'true',
      statusText: '可信'
    }
  ];

  // 为每个新闻项创建卡片，设置递增的动画延迟
  newsItems.forEach((news, index) => {
    const card = document.createElement('div');
    card.className = 'news-card';
    card.style.animationDelay = `${index * 0.2}s`;

    // 获取状态图标
    let statusIcon = '';
    if (news.status === 'true') {
      statusIcon = '<i class="fas fa-check"></i>';
    } else if (news.status === 'false') {
      statusIcon = '<i class="fas fa-times"></i>';
    } else {
      statusIcon = '<i class="fas fa-question"></i>';
    }

    // 设置卡片内容，使用更丰富的HTML结构
    card.innerHTML = `
            <h5>${news.title}</h5>
            <div class="news-meta">
                <span class="news-date"><i class="far fa-calendar-alt"></i> ${news.date}</span>
            </div>
            <div class="news-source">${news.source}</div>
            <div class="news-verification">
                <div class="verification-icon verification-${news.status}">${statusIcon}</div>
                <div class="verification-status">${news.statusText}</div>
            </div>
        `;

    // 添加点击效果
    card.addEventListener('click', () => {
      card.style.transform = 'scale(0.95)';
      setTimeout(() => {
        card.style.transform = '';
      }, 100);
    });

    newsFlow.appendChild(card);
  });
}

// 页面滚动动画
function initScrollAnimation() {
  const elements = document.querySelectorAll('.feature-card, .tool-card, .stat-item');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animation = 'fadeInUp 0.6s ease-out forwards';
      }
    });
  });

  elements.forEach(element => {
    observer.observe(element);
  });
}

// 网络动画
function initNetworkAnimation() {
  const canvas = document.getElementById('networkCanvas');
  if (!canvas) {
    console.log('网络动画画布不存在，跳过网络动画初始化');
    return; // 如果元素不存在，提前退出函数
  }

  const ctx = canvas.getContext('2d');

  // 设置画布大小
  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  // 节点类
  class Node {
    constructor() {
      this.x = Math.random() * canvas.width;
      this.y = Math.random() * canvas.height;
      this.vx = (Math.random() - 0.5) * 2;
      this.vy = (Math.random() - 0.5) * 2;
    }

    update() {
      this.x += this.vx;
      this.y += this.vy;

      if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
      if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
    }
  }

  // 创建节点
  const nodes = Array.from({ length: 50 }, () => new Node());

  // 动画循环
  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 更新和绘制节点
    nodes.forEach(node => {
      node.update();

      // 绘制连线
      nodes.forEach(other => {
        const dx = other.x - node.x;
        const dy = other.y - node.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance < 150) {
          ctx.beginPath();
          ctx.moveTo(node.x, node.y);
          ctx.lineTo(other.x, other.y);
          ctx.strokeStyle = `rgba(255,255,255,${1 - distance / 150})`;
          ctx.stroke();
        }
      });

      // 绘制节点
      ctx.beginPath();
      ctx.arc(node.x, node.y, 3, 0, Math.PI * 2);
      ctx.fillStyle = '#fff';
      ctx.fill();
    });

    requestAnimationFrame(animate);
  }

  animate();
}

// 3D地球动画
function initEarth() {
  const scene = new THREE.Scene();

  // 调整相机位置和视角 - 减小视角使地球看起来更小
  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.z = 4.2;  // 增加距离，让地球看起来更小
  camera.position.x = 0;    // 保持居中
  camera.position.y = 0;    // 保持居中

  // 创建渲染器
  const renderer = new THREE.WebGLRenderer({
    canvas: document.getElementById('earth-canvas'),
    antialias: true,
    alpha: true
  });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setClearColor(0x000000, 0);

  // 减小地球几何体的大小
  const earthGeometry = new THREE.SphereGeometry(1.5, 64, 64);  // 减小地球半径

  // 加载纹理
  const textureLoader = new THREE.TextureLoader();
  const earthTexture = textureLoader.load(STATIC_URL + "frontend/images/features/earth-texture.jpg");
  const bumpTexture = textureLoader.load(STATIC_URL + "frontend/images/features/earth-bump.jpg");
  const specularTexture = textureLoader.load(STATIC_URL + "frontend/images/features/earth-specular.jpg");
  const cloudsTexture = textureLoader.load(STATIC_URL + "frontend/images/features/earth-clouds.png");

  // 调整地球材质
  const earthMaterial = new THREE.MeshPhongMaterial({
    map: earthTexture,
    bumpMap: bumpTexture,
    bumpScale: 0.04,
    specularMap: specularTexture,
    specular: new THREE.Color('grey'),
    shininess: 5,
    opacity: 0.9,
    transparent: true
  });

  // 创建地球网格
  const earth = new THREE.Mesh(earthGeometry, earthMaterial);
  scene.add(earth);

  // 调整云层大小
  const cloudsGeometry = new THREE.SphereGeometry(1.52, 64, 64);  // 相应调整云层大小
  const cloudsMaterial = new THREE.MeshPhongMaterial({
    map: cloudsTexture,
    transparent: true,
    opacity: 0.3
  });
  const clouds = new THREE.Mesh(cloudsGeometry, cloudsMaterial);
  scene.add(clouds);

  // 调整光照位置以适应新的大小
  const directionalLight = new THREE.DirectionalLight(0xffffff, 1.5);
  directionalLight.position.set(6, 3, 6);  // 稍微调整光源位置
  scene.add(directionalLight);

  // 调整点光源范围
  const pointLight = new THREE.PointLight(0x3677ac, 25, 7, 2);
  pointLight.position.set(2.5, 0, 2.5);  // 调整点光源位置
  scene.add(pointLight);

  // 修改动画循环
  function animate() {
    requestAnimationFrame(animate);

    const time = Date.now() * 0.001;

    // 减慢地球自转速度
    earth.rotation.y += 0.0008;
    clouds.rotation.y += 0.001;

    // 轻微的浮动效果
    const floatY = Math.sin(time * 0.5) * 0.05;
    earth.position.y = floatY;
    clouds.position.y = floatY;

    renderer.render(scene, camera);
  }

  // 修改窗口大小变化处理
  function handleResize() {
    const width = window.innerWidth;
    const height = window.innerHeight;

    camera.aspect = width / height;
    camera.updateProjectionMatrix();

    renderer.setSize(width, height);

    const canvas = renderer.domElement;
    canvas.style.width = '100%';
    canvas.style.height = '100%';
  }

  window.addEventListener('resize', handleResize);
  handleResize();
  animate();
}

// 创建星空效果
function createStarField() {
  const starField = document.querySelector('.star-field');
  if (!starField) {
    console.log('星空容器不存在，跳过星空创建');
    return;
  }

  // 创建星星
  for (let i = 0; i < 200; i++) {
    const star = document.createElement('div');
    star.className = 'star';

    // 随机位置
    const x = Math.random() * 100;
    const y = Math.random() * 100;

    // 随机大小
    const size = Math.random() * 2;

    // 随机闪烁周期
    const duration = 3 + Math.random() * 4;

    star.style.cssText = `
        left: ${x}%;
        top: ${y}%;
        width: ${size}px;
        height: ${size}px;
        --duration: ${duration}s;
    `;

    starField.appendChild(star);
  }

  // 创建流星
  setInterval(() => {
    const meteor = document.createElement('div');
    meteor.className = 'meteor';

    // 随机起始位置
    const x = Math.random() * 100 + 50;
    const y = Math.random() * 50;

    // 随机大小和速度
    const size = 1 + Math.random() * 2;
    const duration = 1 + Math.random() * 2;

    meteor.style.cssText = `
        left: ${x}%;
        top: ${y}%;
        width: ${size * 30}px;
        height: ${size}px;
        --duration: ${duration}s;
    `;

    starField.appendChild(meteor);

    // 动画结束后移除流星
    setTimeout(() => {
      meteor.remove();
    }, duration * 1000);
  }, 2000); // 每2秒创建一个新流星
}

// 页面初始化
document.addEventListener('DOMContentLoaded', () => {
  if (typeof createNewsCards === 'function') createNewsCards();
  if (typeof initScrollAnimation === 'function') initScrollAnimation();
  if (typeof initNetworkAnimation === 'function') initNetworkAnimation();
  if (typeof createStarField === 'function') createStarField();
  if (typeof initEarth === 'function' && typeof THREE !== 'undefined') initEarth();

  // 添加特点列表动画延迟
  document.querySelectorAll('.feature-item').forEach((item, index) => {
    item.style.animationDelay = `${index * 0.2}s`;
  });

  // 添加深度分析板块动画
  const analysisBoxes = document.querySelectorAll('.analysis-box');
  analysisBoxes.forEach((box, index) => {
    box.style.animationDelay = `${index * 0.2}s`;
    box.classList.add('fadeInUp');
  });
}); 