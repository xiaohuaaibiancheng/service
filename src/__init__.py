from flask import Flask
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO
from flask_cors import CORS
import datetime
from datetime import timedelta

# 导入配置
from src.config import SECRET_KEY, DEBUG, IMG_FOLDER, ALLOWED_EXTENSIONS

# 创建扩展实例
bcrypt = Bcrypt()
socketio = SocketIO()
cors = CORS()

def create_app():
    """应用工厂函数"""
    app = Flask(__name__)      # 设置静态文件URL前缀
    
    # 基础配置
    app.config.update(
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SECRET_KEY=SECRET_KEY,
        IMG_FOLDER=IMG_FOLDER,
        ALLOWED_EXTENSIONS=ALLOWED_EXTENSIONS,
        DEBUG=DEBUG  # 开发环境下启用调试模式
    )
    
    # 初始化扩展
    bcrypt.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    # 注册路由
    register_frontend_routes(app)  # 注册前端路由
    register_backend_routes(app)   # 注册后端路由
    return app

def register_frontend_routes(app):
    """注册前端路由"""
    # 导入前端路由
    from .frontend.routes import register_routes
    # 注册前端蓝图，使用/frontend作为URL前缀
    register_routes(app)

def register_backend_routes(app):
    """注册后端路由"""
    # 从后端模块导入路由注册函数
    from .backend.routes import register_routes
    # 调用后端的路由注册函数
    register_routes(app)

