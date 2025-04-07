from src import create_app, socketio  


app = create_app()

# 启动应用
if __name__ == "__main__":
    socketio.run(app, debug=True, use_reloader=False)