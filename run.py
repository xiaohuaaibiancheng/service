from src import create_app, socketio  

# 创建应用实例
app = create_app()

# 启动应用
if __name__ == "__main__":
    socketio.run(app, debug=True, use_reloader=False)