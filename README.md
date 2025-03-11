# 虚假新闻检测实时服务系统

这是一个基于Python的虚假新闻检测系统，使用Flask-SocketIO实现实时通信功能，集成了多种AI模型进行新闻真实性分析。

## 功能特点

- 实时Web通信功能（基于Flask-SocketIO）
- 多模态虚假新闻检测（文本、图像、多模态融合）
- AI生成内容检测功能
- 新闻数据可视化与分析
- 用户认证与个人资料管理
- 新闻报告与众包反馈系统
- 教育模块与沙盒测试环境

## 项目结构

```
.
├── run.py              # 主运行文件
├── src/                # 源代码目录
│   ├── __init__.py     # 应用初始化
│   ├── config.py       # 配置文件
│   ├── backend/        # 后台路由与功能
│   ├── frontend/       # 前台路由与功能
│   ├── static/         # 静态资源文件
│   └── templates/      # 前后台模板
├── model/              # 模型相关文件
├── uploads/            # 上传文件目录
├── data/               # 数据文件目录
├── .env                # 环境变量配置文件
└── .env.example        # 环境变量示例文件
```

## 环境要求

- Python 3.10+
- CUDA支持（推荐用于模型加速）
- 其他依赖包请参见 `requirements.txt`

## 安装步骤

1. 克隆项目到本地：
   ```bash
   git clone <repository-url>
   ```

2. 创建并激活虚拟环境（推荐使用conda）：
   ```bash
   conda create --name news_detect python=3.11
   conda activate news_detect
   ```

3. 安装依赖包：
   ```bash
   pip install -r requirements.txt
   ```

4. 配置环境变量：
   ```bash
   # 复制环境变量示例文件
   cp .env.example .env
   
   # 编辑.env文件，填入您的API密钥和其他配置
   # 使用您喜欢的文本编辑器打开.env文件
   ```

## 配置说明

项目使用集中式配置管理，所有配置项都在`src/config.py`文件中定义，并从环境变量中读取值。您可以通过以下方式配置项目：

1. 环境变量：创建`.env`文件并设置相应的环境变量
2. 直接修改`src/config.py`文件中的默认值

主要配置项包括：

- **API密钥**：
  - `OPENAI_API_KEY`：OpenAI API密钥
  - `OPENAI_BASE_URL`：OpenAI API基础URL（可配置为代理）
  - `SERPAPI_API_KEY`：SerpAPI密钥
  - `IMAGE_API_KEY`：图像描述API密钥

- **模型配置**：
  - `OPENAI_MODEL`：使用的OpenAI模型名称（默认为gpt-4o-mini）
  - `EMBEDDING_MODEL`：嵌入模型名称（默认为BAAI/bge-small-zh-v1.5）
  - `EMBEDDING_DEVICE`：运行嵌入模型的设备（cuda/cpu）

- **应用程序配置**：
  - `SECRET_KEY`：Flask应用密钥
  - `DEBUG`：是否启用调试模式

- **其他配置**：
  - `USE_OPENAI_API`：是否使用OpenAI API（否则使用本地模型）
  - `MAX_WORKERS`：最大工作线程数
  - `REQUEST_TIMEOUT`：请求超时时间

详细配置项请参考`.env.example`文件。

## 数据与模型获取
   链接 https://pan.baidu.com/s/14qxSO4LPOJtozEm7hPRHBQ?pwd=dpc3 
   1. model文件夹 - 放在根目录下与src同级
   2. output_data.json - 已检测新闻数据，放在src/static/backend/output_data.json
   3. storage文件夹 - 存放已检测新闻embedding，放在src/static/backend/storage
   4. MultiModal_DeepFake_main文件夹 - 放在src/frontend/MultiModal_DeepFake_main/

## 使用说明

1. 启动服务器：
   ```bash
   python run.py
   ```

2. 打开浏览器访问：
   ```
   http://localhost:5000
   ```

## 主要功能模块

- **新闻检测**：支持URL、文本、图像和多模态内容的虚假新闻检测
- **AI生成内容检测**：检测AI生成的文本和图像
- **新闻聚合与分析**：对新闻数据进行聚合分析和可视化
- **AI助手**：基于检测结果提供事实核查和解释
- **用户管理**：用户注册、登录、个人资料管理
- **教育模块**：提供虚假新闻识别的教育内容和测试
- **报告系统**：允许用户报告可疑新闻并参与众包核查

## 注意事项

- 请确保所有必要的目录都具有适当的读写权限
- 建议在虚拟环境中运行项目
- 首次运行前请确保已安装所有依赖并下载必要的模型文件
- 对于图像处理和大型模型，推荐使用支持CUDA的环境

## 许可证

MIT License

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 Issue
- 发送邮件至：2625464350@qq.com