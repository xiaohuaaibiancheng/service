# 实时服务系统

这是一个基于Python的虚假新闻检测系统，使用Flask-SocketIO实现实时通信功能。

## 功能特点

- 实时Web通信功能
- 文件上传处理
- 模型处理功能

## 项目结构

```
.
├── run.py              # 主运行文件
├── src/                # 源代码目录
├──├───/backend         #后台路由
├──├───/frontend        #前台路由
├──├───/static          #静态数据文件
├──├───/templates       #前后台模板          
├── model/              # 模型相关文件
├── uploads/            # 上传文件目录

```

## 环境要求

- Python 3.10+
- 其他依赖包请参见 `requirements.txt`


## 安装步骤

1. 克隆项目到本地：
   ```bash
   git clone <repository-url>
   ```

2. 创建并激活虚拟环境（推荐使用conda）：
   ```bash
   conda create --name my_env --python=3.11
   
   conda activate my_env

   ```

3. 安装依赖包：
   ```bash
   pip install -r requirements.txt
   ```

## 数据，模型获取
   链接 https://pan.baidu.com/s/14qxSO4LPOJtozEm7hPRHBQ?pwd=dpc3 
   1. model文件夹 放在根目录下跟src一个文件目录下
   2. output_data.json 已检测新闻数据 放在src/static/backend/output_data.json
   3. storage 文件夹 存放已检测新闻embedding 放在src/static/backend/storage
   4. MultiModal_DeepFake_main 文件夹     src/frontend/MultiModal_DeepFake_main/


## 使用说明

1. 启动服务器：
   ```bash
   python run.py
   ```

2. 打开浏览器访问：
   ```
   http://localhost:5000
   ```

## 目录说明

- `src/`: 包含主要的应用程序代码
- `model/`: 存放模型相关文件
- `uploads/`: 存放上传的文件





## 注意事项

- 请确保所有必要的目录都具有适当的读写权限
- 建议在虚拟环境中运行项目
- 首次运行前请确保已安装所有依赖

## 许可证

MIT License

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 Issue
- 发送邮件至：2625464350@qq.com