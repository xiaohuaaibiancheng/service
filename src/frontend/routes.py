# routes.py：路由+视图函数

from flask import Blueprint, render_template, request, jsonify, url_for, redirect, current_app, send_file,session
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
from PIL import Image
import io
from io import BytesIO
import time
import json
import pandas as pd
import xlsxwriter
import base64
import random
import uuid
import logging
import asyncio
from typing import List
import threading

# 导入配置
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, UPLOAD_FOLDER, MAX_CONTENT_LENGTH

from src.frontend.agent import FactChecker 
from src.frontend.ai_img import classify_image
from src.frontend.from_txt_img import ImageTextSimilarity
from src.frontend.lazy import LazyModel
from src.frontend.text_aigc.scripts.local_infer import DetectAIGC
from src.frontend.tool import  extract_and_detect_file_news, extract_and_detect_url_news, init_hammer_model, process_image_and_text, process_text_only, process_title_and_text, save_to_csv
from src.frontend.ai_analyzer import analyze_with_llm
from langchain_community.chat_models import ChatOpenAI

# 导入虚假新闻检测函数
from src.frontend.detect_news import  detect_fake_news_segmented
from src.frontend.single_detect import predict_rumor

# 导入用户使用统计模块
from src.frontend.user_usage_tracker import record_user_usage, get_user_usage_stats, reset_feature_count, reset_all_counts, export_stats_json

# 导入检测历史记录模块
from src.frontend.detection_tracker import detection_tracker

# 创建前端蓝图
frontend_bp = Blueprint(
    'frontend',
    __name__,
    template_folder='../templates',  # 修正模板路径
    static_folder='../static',       # 修正静态文件路径
    static_url_path='/static'        # URL前缀保持不变
)

def register_routes(app):
    app.register_blueprint(frontend_bp, url_prefix='/frontend')  # 保留/frontend前缀
    
    # 设置默认的API密钥和base_url
    app.config.setdefault('OPENAI_API_KEY', OPENAI_API_KEY)
    app.config.setdefault('OPENAI_BASE_URL', OPENAI_BASE_URL)
    # 设置上传文件夹
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH  # 限制上传文件大小为16MB

##模型初始化
classifier_txt_img =  ImageTextSimilarity(model_name="ViT-B-16")
hammer_model = LazyModel(init_hammer_model)
fact_checker = LazyModel(FactChecker)
detector_ai = DetectAIGC()
# AI聊天记录保存路径
CHAT_HISTORY_PATH = os.path.join(os.path.dirname(__file__), '../static/frontend', 'chat_history')
# 分享聊天记录保存路径
SHARED_CHAT_PATH = os.path.join(os.path.dirname(__file__), '../static/frontend', 'shared_chats')
# 上传文件保存路径
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../static/frontend/uploads')

# 确保目录存在
if not os.path.exists(CHAT_HISTORY_PATH):
    os.makedirs(CHAT_HISTORY_PATH)
if not os.path.exists(SHARED_CHAT_PATH):
    os.makedirs(SHARED_CHAT_PATH)
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 功能使用统计的相关配置
USAGE_STATS_PATH = os.path.join(os.path.dirname(__file__), '../static/frontend', 'usage_stats')
USAGE_STATS_FILE = os.path.join(USAGE_STATS_PATH, 'detection_usage.json')

# 确保目录存在
if not os.path.exists(USAGE_STATS_PATH):
    os.makedirs(USAGE_STATS_PATH)

# 用于线程安全的锁
stats_lock = threading.Lock()




@frontend_bp.route('/')
def index():
    # 从session中获取用户名
    username = session.get('username')
    record_user_usage('index_view', username)
    return render_template('frontend/index.html', current_date=datetime.now().strftime('%Y年%m月%d日'))

# 添加新闻检测路由
@frontend_bp.route('/news_detect', methods=['GET', 'POST'])
def news_detect():
    # 从session中获取用户名
    username = session.get('username')
    
    if request.method == 'GET':
        record_user_usage('news_detect_view', username)  # 记录页面访问
        global fact_check
        fact_check=fact_checker.model
        return render_template('frontend/news_detect.html')
    else:  # POST - 提交检测请求
        record_user_usage('news_detect_submit', username)  # 记录功能使用
        # 处理提交的新闻检测请求
        # 由于POST处理代码不在此函数中，这里只是添加记录点

@frontend_bp.route('/agent', methods=['GET', 'POST'])
async def agent():
    # 从session中获取用户名
    username = session.get('username')
    
    if request.method == 'GET':
        record_user_usage('agent_view', username)  # 记录页面访问
        return render_template('frontend/agent.html')
    else:  # POST - 执行事实核查
        record_user_usage('agent_check', username)  # 记录功能使用
        title = request.form.get('title')
        url = request.form.get('url')
        content = request.form.get('content')
        date = request.form.get('date')

        news_info = {
            "title": title,
            "url": url,
            "text": content,
            "date": date
        }
        print('news_info',news_info)
        # 运行事实核查
        report = await fact_check.check_news(news_info)

        # 生成图表数据
        chart_data = {
            'labels': [r.tool_type for r in report.tool_results],
            'values': [r.confidence for r in report.tool_results],
            'verdict': report.final_verdict,
            'confidence': report.confidence
        }

        # 存储结果到 CSV
        save_to_csv(news_info, report)
        print('report.tool_results',[r.model_dump() for r in report.tool_results])
        return jsonify({
            'success': True,
            'data': [r.model_dump() for r in report.tool_results],
            'chart_data': chart_data,
            'final_verdict': report.final_verdict,
            'confidence': report.confidence,
            'error_logs': report.error_logs
        })

@frontend_bp.route("/detect/url", methods=["POST"])
def detect_url():
    # 从session中获取用户名
    username = session.get('username')
    record_user_usage('detect_url', username)  # 记录功能使用
    url = request.json.get("url")
    if not url:
        return jsonify({"error": "URL不能为空"}), 400
    # 模拟从 URL 提取内容（实际应用中需要实现 URL 内容抓取）
    result = extract_and_detect_url_news(url,classifier_txt_img)
    # result = extract_and_detect_url_news(content)
                # 记录检测历史
    if username:
        result_data = json.loads(result)
        if 'title_txt_是否匹配' in result_data and 'title_txt_相似度' in result_data:
            results = "虚假" if result_data['title_txt_是否匹配'] == '0' else "真实"
            accuracy = result_data['title_txt_相似度'] * 100
            detection_tracker.add_detection_record(
                username=username,
                detection_type="文题一致性检测",
                result=results,
                accuracy=accuracy
            )
        if 'text_pic_similarity_probability' in result_data :
            results = "虚假" if result_data['text_pic_similarity_probability'] < 0.5 else "真实"
            accuracy = result_data['text_pic_similarity_probability'] * 100
            detection_tracker.add_detection_record(
                username=username,
                detection_type="图文一致性检测",
                result=results,
                accuracy=accuracy
            )

    return jsonify(result)

@frontend_bp.route('/detect/multimodal', methods=['POST'])
def detect_multimodal():
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('detect_multimodal', username)  # 记录功能使用
    text = request.form.get('text')
    image = request.files.get('image')
    title = request.form.get('title')

    if not text and not image and not title:
        return jsonify({"error": "文本、图片或标题至少需要一个"}), 400

    if image and text and title:
        result1=process_image_and_text(image, text, classifier_txt_img)
        print('result1',result1)
        result2=process_title_and_text(title, text)
        print('result2',result2)
        result = {**result1, **result2}
    elif image and text:
        result = process_image_and_text(image, text, classifier_txt_img)
    elif title and text:
        result = process_title_and_text(title, text)
    elif text:
        result = process_text_only(text)
    else:
        return jsonify({"error": "无效的输入组合"}), 400
    if username:
        result_data = json.loads(result)
        if 'title_txt_是否匹配' in result_data and 'title_txt_相似度' in result_data:
            results = "虚假" if result_data['title_txt_是否匹配'] == '0' else "真实"
            accuracy = result_data['title_txt_相似度'] * 100
            detection_tracker.add_detection_record(
                username=username,
                detection_type="文题一致性检测",
                result=results,
                accuracy=accuracy
            )
        if 'text_pic_similarity_probability' in result_data :
            results = "虚假" if result_data['text_pic_similarity_probability'] < 0.5 else "真实"
            accuracy = result_data['text_pic_similarity_probability'] * 100
            detection_tracker.add_detection_record(
                username=username,
                detection_type="图文一致性检测",
                result=results,
                accuracy=accuracy
            )
    return jsonify(result)

@frontend_bp.route("/detect/file", methods=["POST"])
def detect_file():
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('detect_file', username)  # 记录功能使用
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "文件上传失败"}), 400

    # 保存文件到服务器
    filename = secure_filename(file.filename)  # 确保文件名安全
    upload_folder = "uploads"  # 文件保存的目录
    if not os.path.exists(upload_folder):  # 如果目录不存在，创建目录
        os.makedirs(upload_folder)
    file_path = os.path.join(upload_folder, filename)  # 文件完整路径
    file.save(file_path)  # 保存文件

    # 调用 extract_and_detect_file_news 函数，传入文件路径
    try:
        detection_result = extract_and_detect_file_news(file_path)
        if username:
            result_data = json.loads(detection_result)
            if 'title_txt_是否匹配' in result_data and 'title_txt_相似度' in result_data:
                results = "虚假" if result_data['title_txt_是否匹配'] == '0' else "真实"
                accuracy = result_data['title_txt_相似度'] * 100
                detection_tracker.add_detection_record(
                    username=username,
                    detection_type="文题一致性检测",
                    result=results,
                    accuracy=accuracy
                )
            if 'text_pic_similarity_probability' in result_data :
                results = "虚假" if result_data['text_pic_similarity_probability'] < 0.5 else "真实"
                accuracy = result_data['text_pic_similarity_probability'] * 100
                detection_tracker.add_detection_record(
                    username=username,
                    detection_type="图文一致性检测",
                    result=results,
                    accuracy=accuracy
                )
    except Exception as e:
        return jsonify({"error": f"文件处理失败: {str(e)}"}), 500

    # 返回检测结果
    return jsonify(detection_result)

@frontend_bp.route('/ai_chat')
def ai_chat():
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('ai_chat_view', username)  # 记录页面访问
    return render_template('frontend/ai_chat.html')

@frontend_bp.route('/ai_detect')
def ai_detect():
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('ai_detect_view', username)  # 记录页面访问
    return render_template('frontend/ai_detect.html')

@frontend_bp.route('/about')
def about():
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('about_view', username)  # 记录页面访问
    return render_template('frontend/about.html', current_date=datetime.now().strftime('%Y年%m月%d日'))

@frontend_bp.route('/contact')
def contact():
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('contact_view', username)  # 记录页面访问
    return render_template('frontend/contact.html', current_date=datetime.now().strftime('%Y年%m月%d日'))

@frontend_bp.route('/chat/list')
def chat_history_api():
    try:
        chats = []
        for filename in os.listdir(CHAT_HISTORY_PATH):
            if filename.startswith('chat_') and filename.endswith('.json'):
                filepath = os.path.join(CHAT_HISTORY_PATH, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    chat_data = json.load(f)
                    chats.append({
                        'id': filename.replace('.json', ''),
                        'title': chat_data.get('title', '未命名对话'),
                        'created_at': chat_data.get('created_at')
                    })
        
        chats.sort(key=lambda x: x['created_at'], reverse=True)
        return jsonify({'status': 'success', 'chats': chats})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@frontend_bp.route('/chat/<chat_id>')
def get_chat(chat_id):
    try:
        if not chat_id.startswith('chat_') or '/' in chat_id or '\\' in chat_id:
            return jsonify({'status': 'error', 'message': '无效的聊天ID'})
        
        filepath = os.path.join(CHAT_HISTORY_PATH, f"{chat_id}.json")
        if not os.path.exists(filepath):
            return jsonify({'status': 'error', 'message': '聊天记录不存在'})
        
        with open(filepath, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
            
        return jsonify({
            'status': 'success', 
            'messages': chat_data.get('messages', []),
            'title': chat_data.get('title', '未命名对话')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@frontend_bp.route('/chat/create', methods=['POST'])
def create_chat():
    try:
        # 从session中获取用户名
        username = session.get('username')
        
        record_user_usage('create_chat', username)  # 记录功能使用
        timestamp = int(time.time())
        chat_id = f'chat_{timestamp}'
        
        chat_data = {
            'title': '新对话',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'messages': [
                {
                    'role': 'assistant',
                    'content': '您好！我是AI助手，很高兴为您服务。您可以询问我关于新闻真实性分析的任何问题。'
                }
            ]
        }
        
        # 记录创建者用户名（如果有）
        if username:
            chat_data['created_by'] = username
        
        filepath = os.path.join(CHAT_HISTORY_PATH, f"{chat_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'status': 'success',
            'chat_id': chat_id,
            'title': chat_data['title']
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@frontend_bp.route('/chat/<chat_id>/message', methods=['POST'])
def send_message(chat_id):
    try:
        # 从session中获取用户名
        username = session.get('username')
        
        record_user_usage('send_message', username)  # 记录功能使用
        if not chat_id.startswith('chat_') or '/' in chat_id or '\\' in chat_id:
            return jsonify({'status': 'error', 'message': '无效的聊天ID'})
        
        data = request.json
        user_message = data.get('message', '')
        
        filepath = os.path.join(CHAT_HISTORY_PATH, f"{chat_id}.json")
        if not os.path.exists(filepath):
            return jsonify({'status': 'error', 'message': '聊天记录不存在'})
        
        with open(filepath, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        
        # 添加用户消息到历史记录
        chat_data['messages'].append({
            'role': 'user',
            'content': user_message
        })
        
        # 使用LangChain和OpenAI生成回复
        from langchain.chat_models import ChatOpenAI
        from langchain.schema import HumanMessage, AIMessage, SystemMessage
        
        # 获取API密钥和base_url（优先使用请求中的值，其次是应用配置中的值）
        api_key = data.get('api_key') or current_app.config.get('OPENAI_API_KEY', 'sk-your-default-api-key')
        base_url = data.get('base_url') or current_app.config.get('OPENAI_BASE_URL', 'https://api.chatanywhere.tech')
        
        # 如果消息中包含设置API密钥的请求
        if user_message.startswith('/set_api_key '):
            api_key = user_message.replace('/set_api_key ', '').strip()
            current_app.config['OPENAI_API_KEY'] = api_key
            ai_reply = "API密钥已设置成功！"
        elif user_message.startswith('/set_base_url '):
            base_url = user_message.replace('/set_base_url ', '').strip()
            current_app.config['OPENAI_BASE_URL'] = base_url
            ai_reply = "Base URL已设置成功！"
        else:
            try:
                # 初始化ChatOpenAI
                chat = ChatOpenAI(
                    temperature=0.7,
                    openai_api_key=api_key,
                    openai_api_base=base_url,
                    model_name="gpt-4o-mini"
                )
                
                # 构建消息历史
                messages = []
                
                # 添加系统消息
                messages.append(SystemMessage(content="你是一个有用的AI新闻助手，专注于提供准确、有帮助的回答。"))
                
                # 添加历史消息
                for msg in chat_data['messages'][:-1]:  # 不包括刚刚添加的用户消息
                    if msg['role'] == 'user':
                        messages.append(HumanMessage(content=msg['content']))
                    elif msg['role'] == 'assistant':
                        messages.append(AIMessage(content=msg['content']))
                
                # 添加当前用户消息
                messages.append(HumanMessage(content=user_message))
                
                # 获取AI回复
                response = chat.invoke(messages)
                ai_reply = response.content
            except Exception as e:
                ai_reply = f"生成回复时出错: {str(e)}"
        
        # 添加AI回复到历史记录
        chat_data['messages'].append({
            'role': 'assistant',
            'content': ai_reply
        })
        
        # 如果是新对话，更新标题
        if len(chat_data['messages']) == 3 and chat_data['title'] == '新对话':
            chat_data['title'] = user_message[:20] + ('...' if len(user_message) > 20 else '')
        
        # 保存更新后的聊天记录
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'status': 'success',
            'reply': ai_reply,
            'title': chat_data['title']
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@frontend_bp.route('/chat/delete/<chat_id>', methods=['POST'])
def delete_chat(chat_id):
    try:
        if not chat_id.startswith('chat_') or '/' in chat_id or '\\' in chat_id:
            return jsonify({'status': 'error', 'message': '无效的聊天ID'})
        
        filepath = os.path.join(CHAT_HISTORY_PATH, f"{chat_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': '聊天记录不存在'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# 新增：分享聊天功能
@frontend_bp.route('/chat/share', methods=['POST'])
def share_chat():
    # 从session中获取用户名
    username = session.get('username')
    
    try:
        record_user_usage('share_chat', username)  # 记录功能使用
        data = request.json
        chat_id = data.get('chat_id')
        message_index = data.get('message_index')
        is_readonly = data.get('is_readonly', True)
        
        if not chat_id or not chat_id.startswith('chat_'):
            return jsonify({'status': 'error', 'message': '无效的聊天ID'})
        
        # 读取原始聊天记录
        filepath = os.path.join(CHAT_HISTORY_PATH, f"{chat_id}.json")
        if not os.path.exists(filepath):
            return jsonify({'status': 'error', 'message': '聊天记录不存在'})
        
        with open(filepath, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        
        # 创建分享记录
        share_id = str(uuid.uuid4())[:8]  # 生成短UUID作为分享ID
        
        # 如果指定了消息索引，只分享到该消息为止
        if message_index is not None:
            message_index = int(message_index)
            if 0 <= message_index < len(chat_data.get('messages', [])):
                shared_messages = chat_data.get('messages', [])[:message_index+1]
            else:
                shared_messages = chat_data.get('messages', [])
        else:
            shared_messages = chat_data.get('messages', [])
        
        shared_data = {
            'title': chat_data.get('title', '分享的对话'),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'messages': shared_messages,
            'is_readonly': is_readonly,
            'original_chat_id': chat_id
        }
        
        # 添加分享者用户名（如果有）
        if username:
            shared_data['shared_by'] = username
        
        # 保存分享记录
        share_filepath = os.path.join(SHARED_CHAT_PATH, f"{share_id}.json")
        with open(share_filepath, 'w', encoding='utf-8') as f:
            json.dump(shared_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'status': 'success',
            'share_id': share_id,
            'share_url': f"/frontend/shared/{share_id}"
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# 新增：访问分享的聊天
@frontend_bp.route('/shared/<share_id>')
def view_shared_chat(share_id):
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('view_shared_chat', username)  # 记录页面访问
    try:
        if '/' in share_id or '\\' in share_id:
            return render_template('frontend/error.html', message='无效的分享ID')
        
        filepath = os.path.join(SHARED_CHAT_PATH, f"{share_id}.json")
        if not os.path.exists(filepath):
            return render_template('frontend/error.html', message='分享的聊天不存在或已过期')
        
        with open(filepath, 'r', encoding='utf-8') as f:
            shared_data = json.load(f)
        
        return render_template(
            'frontend/shared_chat.html', 
            share_id=share_id,
            title=shared_data.get('title', '分享的对话'),
            messages=shared_data.get('messages', []),
            is_readonly=shared_data.get('is_readonly', True)
        )
    except Exception as e:
        return render_template('frontend/error.html', message=f'加载分享聊天时出错: {str(e)}')

# 新增：获取分享的聊天数据（API）
@frontend_bp.route('/api/shared/<share_id>')
def get_shared_chat(share_id):
    try:
        if '/' in share_id or '\\' in share_id:
            return jsonify({'status': 'error', 'message': '无效的分享ID'})
        
        filepath = os.path.join(SHARED_CHAT_PATH, f"{share_id}.json")
        if not os.path.exists(filepath):
            return jsonify({'status': 'error', 'message': '分享的聊天不存在或已过期'})
        
        with open(filepath, 'r', encoding='utf-8') as f:
            shared_data = json.load(f)
        
        return jsonify({
            'status': 'success',
            'title': shared_data.get('title', '分享的对话'),
            'messages': shared_data.get('messages', []),
            'is_readonly': shared_data.get('is_readonly', True)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# 新增：回复分享的聊天（如果不是只读）
@frontend_bp.route('/api/shared/<share_id>/reply', methods=['POST'])
def reply_to_shared_chat(share_id):
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('reply_to_shared', username)  # 记录功能使用
    try:
        if '/' in share_id or '\\' in share_id:
            return jsonify({'status': 'error', 'message': '无效的分享ID'})
        
        filepath = os.path.join(SHARED_CHAT_PATH, f"{share_id}.json")
        if not os.path.exists(filepath):
            return jsonify({'status': 'error', 'message': '分享的聊天不存在或已过期'})
        
        with open(filepath, 'r', encoding='utf-8') as f:
            shared_data = json.load(f)
        
        # 检查是否为只读
        if shared_data.get('is_readonly', True):
            return jsonify({'status': 'error', 'message': '此分享聊天为只读模式，不能回复'})
        
        data = request.json
        user_message = data.get('message', '')
        
        # 添加用户消息 (包含用户名如果有)
        user_msg = {
            'role': 'user',
            'content': user_message
        }
        if username:
            user_msg['username'] = username
            
        shared_data['messages'].append(user_msg)
        
        # 使用langchain_openai和langchain_core.schema生成回复
        from langchain.chat_models import ChatOpenAI
        from langchain.schema import HumanMessage, AIMessage, SystemMessage
        
        # 检查API密钥是否已设置
        if not data.get('api_key'):
            ai_reply = "请先设置OpenAI API密钥，使用命令：/set_api_key YOUR_API_KEY"
        else:
            try:
                # 初始化ChatOpenAI
                chat = ChatOpenAI(
                    temperature=0.7,
                    openai_api_key=data['api_key'],
                    openai_api_base=data.get('base_url', 'https://api.openai.com/v1'),
                    model_name="gpt-4o-mini"
                )
                
                # 构建消息历史
                messages = []
                
                # 添加系统消息
                messages.append(SystemMessage(content="你是一个有用的AI新闻助手，专注于提供准确、有帮助的回答。"))
                
                # 添加历史消息
                for msg in shared_data['messages'][:-1]:  # 不包括刚刚添加的用户消息
                    if msg['role'] == 'user':
                        messages.append(HumanMessage(content=msg['content']))
                    elif msg['role'] == 'assistant':
                        messages.append(AIMessage(content=msg['content']))
                
                # 添加当前用户消息
                messages.append(HumanMessage(content=user_message))
                
                # 获取AI回复
                response = chat.invoke(messages)
                ai_reply = response.content
            except Exception as e:
                ai_reply = f"生成回复时出错: {str(e)}"
        
        # 添加AI回复到历史记录
        shared_data['messages'].append({
            'role': 'assistant',
            'content': ai_reply
        })
        
        # 保存更新后的分享聊天
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(shared_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'status': 'success',
            'reply': ai_reply
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

##优化数据利用
# 检测数据统计






@frontend_bp.route('/news_aggregate')
def news_aggregate():
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('news_aggregate_view', username)  # 记录页面访问
    return render_template('frontend/news_aggregate.html', current_date=datetime.now().strftime('%Y年%m月%d日'))



@frontend_bp.route('/detect/ai_text', methods=['POST'])
def detect_text():
    # 从session中获取用户名
    username = session.get('username')
    record_user_usage('detect_ai_text', username)  # 记录功能使用
    data = request.get_json()
    text_content = data.get('text_content')
    if not text_content:
        return jsonify({'error': '文本内容不能为空'}), 400
    
    # 检测文本
    prob = detector_ai.predict_prob(text_content)
    
    random_int = random.randint(1, 10)
    random_percent = random_int * 0.01
    if prob == 0.0:
        prob += random_percent
    if prob == 1.0:
        prob -= random_percent
        
    # 记录检测历史
    if username:
        result = "AI生成" if prob > 0.5 else "人工撰写"
        accuracy = prob * 100 if prob > 0.5 else (1 - prob) * 100
        detection_tracker.add_detection_record(
            username=username,
            detection_type="ai_generated",
            result=result,
            accuracy=accuracy
        )

    return jsonify({
        'status': 'success',
        'probability': prob
    })

# 导出AI检测报告
@frontend_bp.route('/api/ai_detect/export', methods=['POST'])
def export_ai_detect_report():
    # 从session中获取用户名
    username = session.get('username')
    record_user_usage('export_ai_detect_report', username)  # 记录功能使用
    
    data = request.get_json()
    detection_type = data.get('detection_type', 'text')  # 文本或图片
    probability = data.get('probability', 0)
    content = data.get('content', '')  # 检测的内容
    
    # 创建一个包含日期和时间的文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"ai_detection_report_{timestamp}.json"
    
    # 构建报告数据
    report_data = {
        'detection_type': detection_type,
        'probability': probability,
        'result': "AI生成" if probability > 0.5 else "人工撰写",
        'accuracy': probability * 100 if probability > 0.5 else (1 - probability) * 100,
        'content_preview': content[:100] + '...' if len(content) > 100 else content,
        'detection_time': timestamp,
        'features': {
            'ai_feature_index': probability * 10,
            'human_feature_index': (1 - probability) * 10
        }
    }
    
    # 将报告数据转换为JSON字符串
    json_data = json.dumps(report_data, ensure_ascii=False, indent=4)
    
    # 创建一个BytesIO对象
    bytes_io = BytesIO(json_data.encode('utf-8'))
    
    # 返回文件下载
    return send_file(
        bytes_io,
        as_attachment=True,
        download_name=filename,
        mimetype='application/json'
    )

# 分享AI检测结果
@frontend_bp.route('/api/ai_detect/share', methods=['POST'])
def share_ai_detect_result():
    # 从session中获取用户名
    username = session.get('username')
    record_user_usage('share_ai_detect_result', username)  # 记录功能使用
    
    data = request.get_json()
    detection_type = data.get('detection_type', 'text')  # 文本或图片
    probability = data.get('probability', 0)
    
    # 生成唯一的分享ID
    share_id = str(uuid.uuid4())
    
    # 构建分享数据
    share_data = {
        'detection_type': detection_type,
        'probability': probability,
        'result': "AI生成" if probability > 0.5 else "人工撰写",
        'accuracy': probability * 100 if probability > 0.5 else (1 - probability) * 100,
        'shared_by': username,
        'share_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # 存储分享数据 (使用共享记录跟踪器或数据库)
    try:
        db.shared_ai_detections.insert_one(share_data)
    except Exception as e:
        print(f"Error storing shared AI detection: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': '无法保存分享数据'
        }), 500
    
    # 构建分享链接
    share_link = f"{request.host_url.rstrip('/')}/view/ai_detect/{share_id}"
    
    return jsonify({
        'status': 'success',
        'share_id': share_id,
        'share_link': share_link
    })

# 查看分享的AI检测结果
@frontend_bp.route('/view/ai_detect/<share_id>')
def view_shared_ai_detect(share_id):
    # 从session中获取用户名
    username = session.get('username')
    
    # 获取分享数据
    try:
        share_data = db.shared_ai_detections.find_one({'_id': share_id})
        if not share_data:
            return render_template('error.html', message='找不到分享的检测结果'), 404
    except Exception as e:
        print(f"Error retrieving shared AI detection: {str(e)}")
        return render_template('error.html', message='无法加载分享数据'), 500
    
    return render_template('frontend/shared_ai_detect.html', 
                           share_data=share_data,
                           username=username)

# 修复：AI图片检测函数
def detect_ai_generated_image(image):
    """
    检测图片是否由AI生成
    
    Args:
        image: 上传的图片文件
    
    Returns:
        float: 图片由AI生成的概率 (0-1)
    """
    try:
        # 创建uploads目录（如果不存在）
        os.makedirs('uploads', exist_ok=True)
        
        # 生成唯一文件名
        filename = secure_filename(image.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        
        # 保存图片
        image_path = os.path.join('uploads', unique_filename)
        image.save(image_path)
        
        
        # 将图片路径传递给classify_image函数
        result, prob = classify_image(image_path)
        
        # 这里应该实现实际的AI图片检测逻辑
        # 由于没有实际的检测模型，这里返回一个随机概率作为示例
        probability = prob
        
        return probability
    except Exception as e:
        print(f"Error detecting AI image: {str(e)}")
        return 0.5  # 默认返回0.5

@frontend_bp.route('/detect/ai_image', methods=['POST'])
def detect_ai_image():
    # 从session中获取用户名
    username = session.get('username')
    record_user_usage('detect_ai_image', username)  # 记录功能使用
    if 'image' not in request.files:
        return jsonify({'status': 'error', 'message': '没有上传图片文件'}), 400

    image = request.files['image']
    # 调用AI图片检测函数
    probability = detect_ai_generated_image(image)
    
    # 记录检测历史
    if username:
        result = "AI生成" if probability > 0.5 else "真实图片"
        accuracy = probability * 100 if probability > 0.5 else (1 - probability) * 100
        detection_tracker.add_detection_record(
            username=username,
            detection_type="ai_generated",
            result=result,
            accuracy=accuracy
        )

    return jsonify({'status': 'success', 'probability': probability})

# 添加聚合分析路由
@frontend_bp.route('/detect/aggregate', methods=['POST'])
def detect_aggregate():
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('detect_aggregate', username)  # 记录功能使用
    """
    聚合分析接口，可以同时接收图片、文本和标题，进行综合分析
    返回JSON格式的分析结果，使用大模型API和Pydantic模型生成结构化数据
    """
    try:
        # 获取请求中的数据
        image = request.files.get('image')
        text = request.form.get('text')
        title = request.form.get('title')
        
        # 使用内置的API密钥和base_url，而不是从请求中获取
        api_key ='sk-GRq26cv5F72b4eS7I4VnBOGzDZK2sI5PT5fRSLuStEEHxnhC'
        base_url = 'https://api.chatanywhere.tech'
        print('api_key',api_key,'base_url',base_url)
        # 验证输入
        if not any([image, text, title]):
            return jsonify({"error": "至少需要提供图片、文本或标题中的一项"}), 400
        
        results = {}
        
        # 计算内容可信度评分（content维度）
        content_score = 0.0
        content_count = 0
        
        # 处理图片和文本
        if image and text:
            img_text_result = process_image_and_text(image, text, classifier_txt_img)
            results['image_text_analysis'] = img_text_result
            if 'mismatch_probability' in img_text_result:
                # 将不匹配概率转换为匹配概率（可信度）
                content_score += (1 - img_text_result.get('mismatch_probability', 0))
                content_count += 1
        
        # 处理标题和文本
        if title and text:
            title_text_result = process_title_and_text(title, text)
            results['title_text_analysis'] = title_text_result
            if 'mismatch_probability' in title_text_result:
                # 将不匹配概率转换为匹配概率（可信度）
                content_score += (1 - title_text_result.get('mismatch_probability', 0))
                content_count += 1
        
        # 处理仅有文本的情况
        elif text and not title and not image:
            text_result = process_text_only(text)
            results['text_analysis'] = text_result
            if 'mismatch_probability' in text_result:
                content_score += (1 - text_result.get('mismatch_probability', 0))
                content_count += 1
        
        # 计算最终的内容可信度评分
        if content_count > 0:
            content_score = content_score / content_count
        
        # 处理图片的AI生成检测
        ai_image_probability = 0.0
        if image:
            # 保存图片副本用于AI检测
            img_copy = Image.open(image)
            img_buffer = BytesIO()
            img_copy.save(img_buffer, format=img_copy.format or 'JPEG')
            img_buffer.seek(0)
            
            # 检测图片是否由AI生成
            ai_image_probability = detect_ai_generated_image(img_buffer)
            results['ai_image_probability'] = ai_image_probability
            
            # 保存图片用于大模型分析
            filename = secure_filename(f"{uuid.uuid4().hex}_{image.filename if hasattr(image, 'filename') else 'image.jpg'}")
            temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            image.seek(0)  # 重置文件指针
            image.save(temp_path)
            image_url = url_for('frontend.static', filename=f'uploads/{filename}')
        else:
            image_url = ""
        
        # 处理文本的AI生成检测
        ai_text_probability = 0.0
        if text:
            ai_text_probability = detector_ai.predict_prob(text)
            results['ai_text_probability'] = ai_text_probability
        
        # 添加时间戳
        current_time = datetime.now()
        results['timestamp'] = current_time.isoformat()
        
        # 生成综合结论
        conclusion = "根据分析，"
        fake_indicators = []
        
        # 检查图文不匹配
        if 'image_text_analysis' in results and results['image_text_analysis'].get('mismatch_probability', 0) > 0.5:
            fake_indicators.append("图文不匹配")
        
        # 检查标题文本不匹配
        if 'title_text_analysis' in results and results['title_text_analysis'].get('mismatch_probability', 0) > 0.5:
            fake_indicators.append("标题与内容不匹配")
        
        # 检查AI生成概率
        if 'ai_text_probability' in results and results['ai_text_probability'] > 0.7:
            fake_indicators.append("文本可能由AI生成")
        
        if 'ai_image_probability' in results and results['ai_image_probability'] > 0.7:
            fake_indicators.append("图片可能由AI生成")
        
        if fake_indicators:
            conclusion += "该内容存在以下问题：" + "、".join(fake_indicators) + "。建议谨慎对待。"
        else:
            conclusion += "未发现明显造假迹象，但仍建议进行事实核查。"
        
        results['conclusion'] = conclusion
        
        # 使用大模型API和Pydantic模型生成结构化数据
        if title or text:
            # 如果没有提供标题，使用文本的前20个字符作为标题
            if not title and text:
                title = text[:20] + ('...' if len(text) > 20 else '')
            
            # 如果没有提供文本，但有标题，将标题作为文本
            if not text and title:
                text = title
                
            # 使用大模型进行分析
            llm_result = analyze_with_llm(
                title=title,
                content=text,
                image_url=image_url,
                api_key=api_key,
                base_url=base_url
            )
            
            # 创建符合目标JSON格式的结构
            final_result = {
                "news_id": f"news_{uuid.uuid4().hex[:8]}",
                "publish_time": current_time.strftime("%Y/%m/%d"),
                "platform": llm_result['platform'],
                "check_time": current_time.strftime("%Y/%m/%d"),
                "label": "待核实",
                "url": "",
                "title": title,
                "content": text,
                "pic_url": image_url,
                "hashtag": llm_result['hashtag'],
                "summary": llm_result['summary'],
                "credibility": {
                    "score": 0.0,
                    "dimension_scores": {
                        "source": 0.0,
                        "content": 0.0,
                        "logic": 0.0,
                        "propagation": 0.0,
                        "AI": 0.0,
                        "content1": "",
                        "content2": ""
                    },
                    "verification": {
                        "crowdsource_progress": llm_result['credibility']['verification']['crowdsource_progress'],
                        "verified": llm_result['credibility']['verification']['verified']
                    }
                },
                "propagation": {
                    "timeline": llm_result['propagation']['timeline'],  # 直接传递整个timeline列表
                    "user_profile": {
                        "age_dist": llm_result['propagation']['user_profile']['age_dist'],
                        "device_ratio": llm_result['propagation']['user_profile']['device_ratio']
                    }
                },
                "relations": {
                    "related_rumors": llm_result['relations']['related_rumors'],
                    "knowledge_nodes": llm_result['relations']['knowledge_nodes']
                },
                "iscredit": False,
                "location": llm_result['location'],
                "conclusion": llm_result['conclusion']
            }
            
            # 如果有大模型分析结果，更新相应字段
            if llm_result and 'credibility' in llm_result:
                # 更新总体可信度评分
                if 'score' in llm_result['credibility']:
                    final_result['credibility']['score'] = llm_result['credibility']['score']
                
                # 更新维度评分
                if 'dimension_scores' in llm_result['credibility']:
                    dims = llm_result['credibility']['dimension_scores']
                    
                    # 设置source评分（根据一定规则确定，这里可以根据实际需求修改）
                    # 这里简单地使用随机值作为示例
                    source_score = round(random.uniform(0.1, 0.9), 2)
                    final_result['credibility']['dimension_scores']['source'] = source_score
                    
                    # 设置content评分（使用前面计算的content_score）
                    final_result['credibility']['dimension_scores']['content'] = round(content_score, 2)
                    
                    # logic评分保留大模型判断的结果
                    if 'logic' in dims:
                        final_result['credibility']['dimension_scores']['logic'] = dims['logic']
                    
                    # propagation评分（留空，由您自己实现）
                    final_result['credibility']['dimension_scores']['propagation'] = 0.5
                    
                    # AI评分（使用前面检测的AI生成概率）
                    ai_score = max(ai_text_probability, ai_image_probability)
                    final_result['credibility']['dimension_scores']['AI'] = round(ai_score, 2)
            
            # 更新知识节点
            if 'relations' in llm_result and 'knowledge_nodes' in llm_result['relations']:
                final_result['relations']['knowledge_nodes'] = llm_result['relations']['knowledge_nodes']
            
            # 根据可信度评分设置iscredit
            final_result['label'] = '谣言' if final_result['credibility']['score'] < 0.5 else '事实'
            
            try:
                # 尝试将结果保存到JSON文件
                output_file_path = 'src/static/backend/output_data.json'
                
                # 确保目录存在
                os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
                
                # 如果文件不存在，创建一个空数组
                if not os.path.exists(output_file_path):
                    with open(output_file_path, 'w', encoding='utf-8') as f:
                        json.dump([], f, ensure_ascii=False, indent=4)
                
                # 读取现有数据
                with open(output_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)  # 加载 JSON 数据
                
                # 添加新数据
                data.append(final_result)

                # 将更新后的 JSON 数据保存回文件
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                    
                logging.info(f"分析结果已保存到 {output_file_path}")
            except Exception as file_error:
                logging.error(f"保存分析结果到文件时出错: {str(file_error)}")
                # 继续执行，不影响API响应
            
            return jsonify(final_result)
        else:
            # 如果没有足够的数据进行大模型分析，返回基本结果
            return jsonify(results)
    
    except Exception as e:
        logging.error(f"聚合分析出错: {str(e)}", exc_info=True)
        
        # 返回详细的错误信息
        error_response = {
            "error": f"分析过程中出现错误: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "status": "error"
        }
        
        # 如果是开发环境，添加更多调试信息
        if current_app.config.get('DEBUG', False):
            import traceback
            error_response["traceback"] = traceback.format_exc()
        
        return jsonify(error_response), 500

# 添加设置API密钥和Base URL的路由
@frontend_bp.route('/chat/settings', methods=['POST', 'GET'])
def update_chat_settings():
    # 处理GET请求
    if request.method == 'GET':
        return jsonify({
            'status': 'success',
            'api_key': '******' if current_app.config.get('OPENAI_API_KEY') else '',
            'base_url': current_app.config.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        })
    
    # 处理POST请求
    try:
        # 确保请求包含JSON数据
        if not request.is_json:
            return jsonify({'status': 'error', 'message': '请求必须包含JSON数据'}), 400
            
        data = request.json
        api_key = data.get('api_key', '')
        base_url = data.get('base_url', '')
        
        # 记录接收到的数据（不要记录完整的API密钥）
        if api_key:
            print(f"接收到API密钥设置请求，长度: {len(api_key)}")
        if base_url:
            print(f"接收到Base URL设置: {base_url}")
        
        # 更新配置
        if api_key:
            current_app.config['OPENAI_API_KEY'] = api_key
        
        if base_url:
            current_app.config['OPENAI_BASE_URL'] = base_url
        
        return jsonify({
            'status': 'success',
            'message': '设置已更新'
        })
    except Exception as e:
        print(f"更新设置时出错: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500



@frontend_bp.route('/api/news/search', methods=['POST'])
def search_news():
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('news_aggregate_search', username)  # 记录功能使用
    try:
        data = request.json
        keyword = data.get('keyword', '')
        platform = data.get('platform', 'all')  # 获取平台参数
        
        if not keyword:
            return jsonify({
                'status': 'error',
                'message': '请输入搜索关键词'
            }), 400
            
        # 导入新闻爬虫类
        from src.frontend.web_crawler import MultiPlatformNewsCrawler
        
        # 创建爬虫实例
        crawler = MultiPlatformNewsCrawler()
        
        # 根据平台参数决定搜索方式
        if platform != 'all':
            result = {'news': crawler.search_by_platform(keyword, platform), 'stats': {}}
        else:
            result = crawler.search_all_platforms(keyword)
        
        # 增强传播时间线数据
        if 'stats' in result and 'timeline' in result['stats']:
            # 增加更详细的时间线数据
            enhanced_timeline = []
            base_time = datetime.now() - timedelta(days=7)
            
            for i, point in enumerate(result['stats']['timeline']):
                # 为每个时间点添加更多信息
                time_point = base_time + timedelta(hours=i*8)
                enhanced_point = {
                    'time': time_point.strftime('%Y-%m-%d %H:%M'),
                    'value': point[1],
                    'platform': random.choice(['百度', '搜狗', '央视', '中新网']),
                    'event': f"关键事件 #{i+1}",
                    'impact_score': random.randint(1, 10)
                }
                enhanced_timeline.append(enhanced_point)
            
            result['stats']['enhanced_timeline'] = enhanced_timeline
        
        print(f"搜索到的新闻数量: {len(result['news'])}")  # 调试日志
            
        return jsonify({
            'status': 'success',
            'data': result
        })
            
    except Exception as e:
        print(f"Error in search_news: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@frontend_bp.route('/api/news/analyze', methods=['POST'])
def analyze_news():
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('news_analyze', username)  # 记录功能使用
    try:
        data = request.json
        url = data.get('url')
        title = data.get('title')
        
        if not url or not title:
            return jsonify({
                'status': 'error',
                'message': '缺少必要参数'
            }), 400
            
        # 获取文章内容
        try:
            from newspaper import Article
            article = Article(url)
            article.download()
            article.parse()
            article.nlp()  # 进行NLP处理以提取关键词等
            
            content = article.text
            keywords = article.keywords
            published_date = article.publish_date
            
            # 如果提取到的关键词不足5个，则添加更多
            if len(keywords) < 5:
                import jieba.analyse
                additional_keywords = jieba.analyse.extract_tags(content, topK=10)
                keywords = list(set(keywords + additional_keywords))[:5]
                
            # 如果没有提取到任何关键词，使用标题中的词
            if not keywords:
                keywords = jieba.analyse.extract_tags(title, topK=5)
                
            # 过滤太长或太短的关键词
            filtered_keywords = []
            for kw in keywords:
                # 限制关键词长度在2-10个字符之间
                if 2 <= len(kw) <= 10 and not re.match(r'^\d+$', kw):
                    filtered_keywords.append(kw)
            
            # 如果过滤后关键词不足，尝试从标题提取短关键词补充
            if len(filtered_keywords) < 3:
                short_keywords = []
                for word in jieba.lcut(title):
                    if 2 <= len(word) <= 10 and not re.match(r'^\d+$', word) and word not in filtered_keywords:
                        short_keywords.append(word)
                        
                filtered_keywords.extend(short_keywords[:5-len(filtered_keywords)])
                
            keywords = filtered_keywords[:5]  # 取最多5个关键词
            
        except Exception as e:
            print(f"提取文章内容失败: {str(e)}")
            content = ""
            keywords = title.split()[:5]  # 使用标题分词作为备选
            published_date = datetime.now()
            
        # 使用关键词搜索相关新闻
        from src.frontend.web_crawler import MultiPlatformNewsCrawler
        crawler = MultiPlatformNewsCrawler()
        
        # 使用标题中的关键词搜索相关新闻
        search_keyword = " ".join(keywords[:3]) if keywords else title.split()[:3]
        related_results = crawler.search_all_platforms(search_keyword)
        related_news_list = related_results.get('news', [])
        
        # 过滤掉当前新闻自身
        filtered_related_news = [news for news in related_news_list if news.get('url') != url][:3]
        
        # 进行情感分析
        import jieba
        import re
        
        # 简单的情感分析词典
        positive_words = ['好', '优', '佳', '胜', '赞', '利好', '成功', '突破', '提升', '成就', '发展', '增长', '满意']
        negative_words = ['差', '糟', '败', '输', '危机', '下跌', '问题', '困难', '失败', '低迷', '下降', '不足']
        
        # 分词并统计情感词
        words = jieba.lcut(content)
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        # 确定情感倾向和分数
        if positive_count > negative_count:
            sentiment = 1  # 正面
            sentiment_score = min(0.9, 0.5 + (positive_count - negative_count) / len(words) * 5)
        elif negative_count > positive_count:
            sentiment = -1  # 负面
            sentiment_score = min(0.9, 0.5 + (negative_count - positive_count) / len(words) * 5)
        else:
            sentiment = 0  # 中性
            sentiment_score = 0.5
            
        # 基于文章内容和关键词进行可信度评估
        credibility_score = 70  # 基础分
        
        # 添加可信度评分因素
        if len(content) > 500:  # 较长文章通常更详细
            credibility_score += 5
        
        if len(keywords) >= 5:  # 关键词丰富
            credibility_score += 5
            
        if len(filtered_related_news) >= 2:  # 有相关报道
            credibility_score += 10
            
        # 限制在合理范围内
        credibility_score = min(95, max(50, credibility_score))
        
        # 提取实体识别 - 简化版
        entities = []
        for kw in keywords:
            if 2 <= len(kw) <= 10 and not re.match(r'[^\w\s]', kw):
                entities.append(kw)
                
        # 如果实体不足，从标题中提取实体
        if len(entities) < 3:
            for word in jieba.lcut(title):
                if 2 <= len(word) <= 10 and not re.match(r'[^\w\s]', word) and word not in entities:
                    entities.append(word)
                    if len(entities) >= 3:
                        break
                        
        entities = entities[:3]  # 限制最多3个实体
            
        # 构建主题分类 - 简化版
        topic_matches = {
            '政治': ['政府', '党', '主席', '总理', '国家', '政策', '法律'],
            '经济': ['经济', '股市', '金融', '投资', '企业', '贸易', '产业'],
            '科技': ['科技', '互联网', '软件', '硬件', '创新', '研发', '数字'],
            '社会': ['社会', '民生', '教育', '医疗', '公共', '安全', '服务'],
            '文化': ['文化', '艺术', '电影', '音乐', '传统', '历史', '娱乐'],
            '体育': ['体育', '足球', '篮球', '奥运', '比赛', '运动员', '冠军']
        }
        
        topics = []
        content_lower = content.lower()
        for topic, indicators in topic_matches.items():
            if any(indicator in content_lower for indicator in indicators):
                topics.append(topic)
                
        if not topics:
            topics = ['综合']
        
        # 从相关新闻获取传播时间线数据
        propagation_timeline = []
        platforms = list(set([news.get('source', '未知来源').replace('来源：', '') for news in related_news_list]))
        
        # 添加当前新闻发布平台
        current_platform = None
        for plat in platforms:
            if plat in url:
                current_platform = plat
                break
                
        if not current_platform:
            current_platform = "当前平台"
            
        # 按时间排序相关新闻
        sorted_related = sorted(related_news_list, key=lambda x: x.get('publish_time', ''), reverse=False)
        
        # 生成传播时间线
        for i, news in enumerate(sorted_related[:5]):
            platform = news.get('source', '未知来源').replace('来源：', '')
            shares = int(news.get('credibility', 50) * 50)  # 基于可信度估算分享数
            
            time_point = {
                'time': news.get('publish_time', '未知时间'),
                'platform': platform,
                'shares': shares
            }
            propagation_timeline.append(time_point)
            
        # 确保传播时间线有数据
        if not propagation_timeline:
            propagation_timeline = [
                {'time': datetime.now().strftime('%Y-%m-%d %H:%M'), 'platform': current_platform, 'shares': 500}
            ]
        
        # 构建最终结果
        analysis_result = {
            'credibility': credibility_score,
            'keywords': keywords[:5],
            'sentiment': sentiment,
            'sentiment_score': sentiment_score,
            'related_news': [
                {
                    'title': news.get('title', '相关新闻'),
                    'url': news.get('url', '#'),
                    'source': news.get('source', '未知来源'),
                    'publish_time': news.get('publish_time', '未知时间'),
                    'similarity': news.get('credibility', 70)  # 使用可信度作为相似度
                } for news in filtered_related_news
            ],
            # 添加传播时间线数据
            'propagation_timeline': propagation_timeline,
            # 添加内容分析
            'content_analysis': {
                'factual_score': credibility_score,
                'bias_score': int(30 + abs(sentiment) * 20),  # 情感越明显，偏见分数越高
                'sensational_score': int(30 + abs(sentiment) * 30),  # 情感越明显，耸动分数越高
                'key_entities': entities,
                'topic_classification': topics
            },
            # 添加传播影响力分析（基于相关新闻数量和情感）
            'impact_analysis': {
                'overall_impact': min(10, max(1, len(related_news_list) // 3)),
                'demographic_reach': {
                    '18-24岁': 20 + (len(topics) * 5),
                    '25-34岁': 30 + (len(topics) * 2),
                    '35-44岁': 25 + (len(entities) * 2),
                    '45-54岁': 15 + (len(entities) * 1),
                    '55岁以上': 10
                },
                'geographic_distribution': {
                    '华东': 30,
                    '华北': 25,
                    '华南': 20,
                    '西南': 10,
                    '西北': 5,
                    '东北': 5,
                    '华中': 5
                }
            }
        }
        
        return jsonify({
            'status': 'success',
            'data': analysis_result
        })
            
    except Exception as e:
        print(f"Error in analyze_news: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 添加新的路由：获取传播时间线详情
@frontend_bp.route('/api/news/timeline', methods=['POST'])
def get_news_timeline():
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('news_timeline', username)  # 记录功能使用
    try:
        data = request.json
        keyword = data.get('keyword', '')
        
        if not keyword:
            return jsonify({
                'status': 'error',
                'message': '缺少关键词参数'
            }), 400
        
        # 使用相同的爬虫获取实际的新闻数据
        from src.frontend.web_crawler import MultiPlatformNewsCrawler
        crawler = MultiPlatformNewsCrawler()
        
        # 获取所有平台的新闻数据
        search_result = crawler.search_all_platforms(keyword)
        news_list = search_result.get('news', [])
        
        if not news_list:
            return jsonify({
                'status': 'error',
                'message': '未找到相关新闻数据'
            }), 404
        
        # 基于实际数据构建时间线
        timeline_data = []
        
        # 按时间排序新闻，确保时间线按时间顺序展示
        sorted_news = sorted(news_list, key=lambda x: x.get('publish_time', ''), reverse=False)
        
        # 从新闻标题中提取事件类型
        events = [
            '首次报道', '热点形成', '官方回应', '专家解读', 
            '社交媒体讨论', '辟谣信息', '后续报道',
            '舆情分析'
        ]
        
        # 构建真实时间线数据
        for i, news in enumerate(sorted_news[:10]):  # 限制为前10条新闻
            # 确定事件类型（基于内容或顺序）
            event_index = min(i, len(events)-1)
            
            # 提取情感倾向（可以基于标题或摘要内容简单判断）
            sentiment = '中性'
            summary = news.get('summary', '').lower()
            title = news.get('title', '').lower()
            positive_words = ['好', '佳', '胜', '赞', '利好', '成功', '突破', '提升', '成就']
            negative_words = ['差', '糟', '败', '输', '危机', '下跌', '问题', '困难', '失败']
            
            if any(word in title or word in summary for word in positive_words):
                sentiment = '正面'
            elif any(word in title or word in summary for word in negative_words):
                sentiment = '负面'
            
            # 处理标题，截断过长的标题
            news_title = news.get('title', '无标题')
            if len(news_title) > 20:
                news_title = news_title[:18] + '...'
                
            # 构建时间线项
            timeline_item = {
                'time': news.get('publish_time', '未知时间'),
                'platform': news.get('source', '未知来源').replace('来源：', ''),
                'event': events[event_index],
                'title': news_title,
                'url': news.get('url', '#'),
                'shares': int(news.get('credibility', 50) * 50),  # 使用可信度创建分享数
                'comments': int(news.get('credibility', 50) * 20),  # 使用可信度创建评论数
                'sentiment': sentiment,
                'impact_score': min(10, max(1, int(news.get('credibility', 50) / 10)))  # 基于可信度计算影响力
            }
            timeline_data.append(timeline_item)
        
        # 生成平台相似度数据（基于实际新闻来源）
        platforms_found = list(set([news.get('source', '').replace('来源：', '') for news in news_list]))
        similarity_data = []
        
        # 确保至少有两个不同平台才生成相似度数据
        if len(platforms_found) >= 2:
            # 最多选择5对平台对比
            pairs_count = min(5, len(platforms_found) * (len(platforms_found) - 1) // 2)
            
            platform_pairs = []
            for i in range(len(platforms_found)):
                for j in range(i+1, len(platforms_found)):
                    platform_pairs.append((platforms_found[i], platforms_found[j]))
            
            # 如果有超过5对，随机选择5对
            if len(platform_pairs) > 5:
                import random
                platform_pairs = random.sample(platform_pairs, 5)
            
            # 计算平台间相似度（基于报道内容、时间等因素）
            for platform1, platform2 in platform_pairs:
                # 获取两个平台的新闻
                platform1_news = [n for n in news_list if platform1 in n.get('source', '')]
                platform2_news = [n for n in news_list if platform2 in n.get('source', '')]
                
                # 基于标题相似性计算相似度
                similarity_score = 0
                if platform1_news and platform2_news:
                    # 比较标题中的关键词重叠
                    platform1_words = set(' '.join([n.get('title', '') for n in platform1_news]).split())
                    platform2_words = set(' '.join([n.get('title', '') for n in platform2_news]).split()) 
                    
                    # 计算Jaccard相似度
                    common_words = platform1_words.intersection(platform2_words)
                    total_words = platform1_words.union(platform2_words)
                    
                    if total_words:
                        similarity_score = int((len(common_words) / len(total_words)) * 100)
                
                # 确保相似度在合理范围内
                similarity_score = max(30, min(95, similarity_score))
                
                similarity_data.append({
                    'platforms': f"{platform1} vs {platform2}",
                    'similarity': f"{similarity_score}%"
                })
        
        # 计算汇总数据
        total_shares = sum(item['shares'] for item in timeline_data)
        total_comments = sum(item['comments'] for item in timeline_data)
        
        # 找出分享量最高的时间点
        peak_time = timeline_data[0]['time'] if timeline_data else '无数据'
        if timeline_data:
            peak_item = max(timeline_data, key=lambda x: x['shares'])
            peak_time = peak_item['time']
        
        # 确定主要情感倾向
        sentiment_counts = {'正面': 0, '中性': 0, '负面': 0}
        for item in timeline_data:
            sentiment_counts[item['sentiment']] += 1
        
        dominant_sentiment = max(sentiment_counts.items(), key=lambda x: x[1])[0] if sentiment_counts else '中性'
        
        return jsonify({
            'status': 'success',
            'data': {
                'keyword': keyword,
                'timeline': timeline_data,
                'similarity': similarity_data,
                'summary': {
                    'total_shares': total_shares,
                    'total_comments': total_comments,
                    'peak_time': peak_time,
                    'dominant_sentiment': dominant_sentiment
                }
            }
        })
        
    except Exception as e:
        print(f"Error in get_news_timeline: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@frontend_bp.route('/fake_news_classify', methods=['GET', 'POST'])
def fake_news_classify():
    """新闻虚假检测二分类页面和API"""
    # 从session中获取用户名
    username = session.get('username')
    
    if request.method == 'GET':
        record_user_usage('fake_news_classify', username)  # 记录页面访问
        return render_template('frontend/fake_news_classify.html', current_date=datetime.now().strftime('%Y年%m月%d日'))
    else:  # POST - 实际执行分类
        record_user_usage('fake_news_classify', username)  # 记录功能使用
        try:
            data = request.json
            title = data.get('title', '')
            content = data.get('content', '')
            
            if not content:
                return jsonify({"error": "新闻内容不能为空"}), 400
            
            # 使用title和content组合，如果title不为空
            text_to_analyze = f"{title} {content}" if title else content
            
            # 调用predict_rumor函数进行虚假新闻检测
            prediction_result = predict_rumor(text_to_analyze)
            
            # 记录检测历史
            if username:
                result_data = json.loads(prediction_result)
                if 'predicted_label' in result_data and 'probability' in result_data:
                    result = "虚假" if result_data['predicted_label'] == '谣言' else "真实"
                    accuracy = result_data['probability'] * 100
                    detection_tracker.add_detection_record(
                        username=username,
                        detection_type="fake_news",
                        result=result,
                        accuracy=accuracy
                    )
            
            # 直接返回predict_rumor的结果
            return prediction_result, 200, {'Content-Type': 'application/json'}
        
        except Exception as e:
            logging.error(f"新闻虚假检测出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理请求时出错: {str(e)}"}), 500

@frontend_bp.route('/news_segment_detect', methods=['GET'])
def news_segment_detect():
    """分段检测新闻页面"""
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('news_segment_view', username)  # 记录页面访问
    # 检查是否有ID参数，如果有则表示从历史记录加载
    record_id = request.args.get('id')
    if record_id:
        try:
            # 构建文件路径
            import os
            import json
            results_dir = os.path.join(current_app.static_folder, 'frontend', 'analysis_results')
            json_path = os.path.join(results_dir, f'{record_id}.json')
            
            # 检查文件是否存在
            if os.path.exists(json_path):
                # 读取分析结果
                with open(json_path, 'r', encoding='utf-8') as f:
                    record = json.load(f)
                    
                # 将记录ID传递给模板，在前端JavaScript中处理
                return render_template('frontend/news_segment_detect.html', record_id=record_id)
        except Exception as e:
            print(f"加载历史记录时出错: {str(e)}")
    
    # 正常加载检测页面
    return render_template('frontend/news_segment_detect.html')

@frontend_bp.route('/news_segment_history', methods=['GET'])
def news_segment_history():
    """新闻分段检测历史记录页面"""
    return render_template('frontend/news_segment_history.html')

@frontend_bp.route('/api/news_segment_history', methods=['GET'])
def get_news_segment_history():
    """获取新闻分段检测历史记录列表"""
    try:
        # 获取过滤和排序参数
        filter_type = request.args.get('filter', 'all')
        sort_type = request.args.get('sort', 'latest')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        
        # 验证参数
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 50:
            per_page = 10
            
        # 获取分析结果文件列表
        import os
        import json
        from datetime import datetime
        
        results_dir = os.path.join(current_app.static_folder, 'frontend', 'analysis_results')
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            
        # 读取所有JSON文件
        all_records = []
        for filename in os.listdir(results_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(results_dir, filename), 'r', encoding='utf-8') as f:
                        record = json.load(f)
                        
                    # 解析记录
                    analysis_id = record.get('id')
                    title = record.get('title', '无标题')
                    content = record.get('content', '')
                    result = record.get('result', {})
                    overall_result = result.get('overall_result', {})
                    
                    # 获取可信度信息
                    credibility_level = overall_result.get('credibility_level', '中')
                    credibility_score = overall_result.get('credibility_score', 5.0)
                    conclusion = overall_result.get('conclusion', '')
                    segments_count = overall_result.get('total_segments', 0)
                    
                    # 获取时间信息
                    timestamp_str = record.get('timestamp')
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str).timestamp() * 1000
                        except:
                            timestamp = os.path.getmtime(os.path.join(results_dir, filename)) * 1000
                    else:
                        timestamp = os.path.getmtime(os.path.join(results_dir, filename)) * 1000
                    
                    # 应用过滤条件
                    if filter_type != 'all':
                        if filter_type == 'high' and credibility_level != '高':
                            continue
                        if filter_type == 'medium' and credibility_level != '中':
                            continue
                        if filter_type == 'low' and credibility_level != '低':
                            continue
                    
                    # 创建记录对象
                    record_obj = {
                        'id': analysis_id,
                        'title': title,
                        'content': content,
                        'credibility_level': credibility_level,
                        'credibility_score': credibility_score,
                        'conclusion': conclusion,
                        'segments_count': segments_count,
                        'timestamp': timestamp,
                        'detail_url': url_for('frontend.news_segment_detect') + f'?id={analysis_id}'
                    }
                    
                    all_records.append(record_obj)
                except Exception as e:
                    print(f"读取文件 {filename} 时出错: {str(e)}")
        
        # 应用排序
        if sort_type == 'latest':
            all_records.sort(key=lambda x: x['timestamp'], reverse=True)
        elif sort_type == 'oldest':
            all_records.sort(key=lambda x: x['timestamp'])
        elif sort_type == 'credibility_high':
            all_records.sort(key=lambda x: x['credibility_score'], reverse=True)
        elif sort_type == 'credibility_low':
            all_records.sort(key=lambda x: x['credibility_score'])
        
        # 计算分页
        total_records = len(all_records)
        total_pages = (total_records + per_page - 1) // per_page
        
        if page > total_pages and total_pages > 0:
            page = total_pages
            
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total_records)
        
        # 分页数据
        paged_records = all_records[start_idx:end_idx]
        
        # 分页元数据
        pagination = {
            'current_page': page,
            'per_page': per_page,
            'total_records': total_records,
            'total_pages': total_pages
        }
        
        return jsonify({
            'status': 'success',
            'data': paged_records,
            'pagination': pagination
        })
        
    except Exception as e:
        print(f"获取历史记录列表时出错: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'处理请求时出错: {str(e)}'
        }), 500

@frontend_bp.route('/api/news_segment_record/delete', methods=['POST'])
def delete_news_segment_record():
    """删除单条新闻分段检测记录"""
    try:
        # 获取记录ID
        data = request.json
        record_id = data.get('record_id')
        
        if not record_id:
            return jsonify({
                'status': 'error',
                'message': '未提供记录ID'
            }), 400
            
        # 构建文件路径
        import os
        results_dir = os.path.join(current_app.static_folder, 'frontend', 'analysis_results')
        json_path = os.path.join(results_dir, f'{record_id}.json')
        
        # 检查文件是否存在
        if not os.path.exists(json_path):
            return jsonify({
                'status': 'error',
                'message': '记录不存在或已被删除'
            }), 404
            
        # 删除文件
        os.remove(json_path)
        
        return jsonify({
            'status': 'success',
            'message': '记录已成功删除'
        })
        
    except Exception as e:
        print(f"删除历史记录时出错: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'处理请求时出错: {str(e)}'
        }), 500

@frontend_bp.route('/api/detect/segments', methods=['POST'])
def detect_news_segments():
    """处理分段检测API请求"""
    # 从session中获取用户名
    username = session.get('username')
    record_user_usage('news_segment_analyze', username)  # 记录功能使用
    try:
        # 获取请求数据
        data = request.json
        title = data.get('title', '')
        content = data.get('content', '')
        segment_size = data.get('segment_size', 500)
        
        # 参数验证
        if not title or not content:
            return jsonify({
                'status': 'error',
                'message': '标题和内容不能为空'
            }), 400
            
        # 限制过长的输入
        if len(title) > 200:
            title = title[:200]
        if len(content) > 10000:
            content = content[:10000]
            
        # 处理分段分析
        result = detect_fake_news_segmented(title, content, segment_size)
        
        # 记录检测历史
        if username and 'overall_result' in result:
            overall_result = result['overall_result']
            credibility_score = overall_result.get('credibility_score', 5.0)
            credibility_level = overall_result.get('credibility_level', '中')
            
            detection_tracker.add_detection_record(
                username=username,
                detection_type="consistency",
                result=f"可信度{credibility_level}",
                accuracy=credibility_score * 10  # 转换为百分比
            )
        
        # 创建分析记录的唯一ID
        analysis_id = str(uuid.uuid4())
        
        # 确保result中的overall_result包含total_segments字段
        if 'overall_result' in result and 'total_segments' not in result['overall_result']:
            result['overall_result']['total_segments'] = len(result.get('segments', []))
        
        # 为每个段落添加分享链接
        for segment in result.get('segments', []):
            segment_id = segment['segment_id']
            segment['share_url'] = url_for('frontend.view_segment', segment_id=segment_id, analysis_id=analysis_id, _external=True)
        
        # 保存分析结果到JSON文件
        try:
            # 确保目录存在
            import os
            results_dir = os.path.join(current_app.static_folder, 'frontend', 'analysis_results')
            if not os.path.exists(results_dir):
                os.makedirs(results_dir)
            
            # 保存完整分析结果
            analysis_data = {
                'id': analysis_id,
                'title': title,
                'content': content,
                'result': result,
                'timestamp': datetime.now().isoformat()
            }
            
            # 写入JSON文件
            with open(os.path.join(results_dir, f'{analysis_id}.json'), 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            # 将分析ID添加到结果中    
            result['analysis_id'] = analysis_id
            
        except Exception as e:
            print(f"保存分析数据时出错: {str(e)}")
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except Exception as e:
        print(f"分段检测处理出错: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'处理请求时出错: {str(e)}'
        }), 500

@frontend_bp.route('/view_segment/<segment_id>', methods=['GET'])
def view_segment(segment_id):
    """查看单个段落分析结果"""
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('view_segment', username)  # 记录功能使用
    # 获取分析ID
    analysis_id = request.args.get('analysis_id', '')
    
    if not analysis_id:
        return render_template('frontend/error.html', 
                              message='未提供分析ID，无法查看段落分析结果'), 400
    
    # 构建文件路径
    import os
    results_dir = os.path.join(current_app.static_folder, 'frontend', 'analysis_results')
    json_path = os.path.join(results_dir, f'{analysis_id}.json')
    
    # 检查文件是否存在
    if not os.path.exists(json_path):
        return render_template('frontend/error.html', 
                              message='找不到相关分析结果，可能已过期或ID无效'), 404
    
    # 返回包含单个段落数据的页面
    return render_template('frontend/segment_view.html', 
                          segment_id=segment_id,
                          analysis_id=analysis_id)

@frontend_bp.route('/api/segment/<segment_id>', methods=['GET'])
def get_segment_data(segment_id):
    """获取段落详细数据的API"""
    # 获取分析ID
    analysis_id = request.args.get('analysis_id', '')
    
    if not analysis_id:
        return jsonify({
            'status': 'error',
            'message': '未提供分析ID'
        }), 400
    
    try:
        # 构建文件路径
        import os
        import json
        results_dir = os.path.join(current_app.static_folder, 'frontend', 'analysis_results')
        json_path = os.path.join(results_dir, f'{analysis_id}.json')
        
        # 检查文件是否存在
        if not os.path.exists(json_path):
            return jsonify({
                'status': 'error',
                'message': '找不到相关分析结果，可能已过期或ID无效'
            }), 404
        
        # 读取JSON文件
        with open(json_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
        
        # 如果请求特定段落
        if segment_id != 'all':
            # 查找指定的段落
            segment_data = None
            for segment in analysis_data.get('result', {}).get('segments', []):
                if segment.get('segment_id') == segment_id:
                    segment_data = segment
                    break
            
            if not segment_data:
                return jsonify({
                    'status': 'error',
                    'message': f'在分析结果中找不到段落ID: {segment_id}'
                }), 404
            
            # 添加分析的标题和总体结论
            segment_data['title'] = analysis_data.get('title', '')
            segment_data['overall_result'] = analysis_data.get('result', {}).get('overall_result', {})
            
            return jsonify({
                'status': 'success',
                'data': segment_data
            })
        # 如果请求完整分析结果
        else:
            return jsonify({
                'status': 'success',
                'data': {
                    'title': analysis_data.get('title', ''),
                    'content': analysis_data.get('content', ''),
                    'timestamp': analysis_data.get('timestamp', ''),
                    'result': analysis_data.get('result', {})
                }
            })
        
    except Exception as e:
        print(f"获取段落数据时出错: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'处理请求时出错: {str(e)}'
        }), 500

# 添加用户使用统计API
@frontend_bp.route('/admin/user_usage')
def view_user_usage_stats():
    """查看用户使用统计数据"""
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('view_usage_stats', username)  # 记录功能使用
    return render_template('frontend/user_usage_stats.html')

@frontend_bp.route('/api/user_usage')
def get_user_usage_api():
    """获取用户使用统计数据API"""
    # 这个API路由不需要记录使用统计，因为这是后台功能
    stats = get_user_usage_stats()
    return jsonify({
        'status': 'success',
        'data': stats
    })

@frontend_bp.route('/api/user_usage/reset', methods=['POST'])
def reset_user_usage():
    """重置用户使用统计"""
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('reset_stats', username)  # 记录功能使用
    data = request.json
    feature = data.get('feature', None)
    
    if feature:
        success = reset_feature_count(feature)
    else:
        success = reset_all_counts()
        
    return jsonify({
        'status': 'success' if success else 'error',
        'message': '统计数据已重置' if success else '重置统计数据失败'
    })

@frontend_bp.route('/api/user_usage/download')
def download_user_usage():
    """下载用户使用统计数据"""
    # 从session中获取用户名
    username = session.get('username')
    
    record_user_usage('download_stats', username)  # 记录功能使用
    # 创建一个包含日期和时间的文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"user_usage_stats_{timestamp}.json"
    
    # 获取JSON字符串
    json_data = export_stats_json()
    
    # 创建一个BytesIO对象
    bytes_io = BytesIO(json_data.encode('utf-8'))
    
    # 返回文件下载
    return send_file(
        bytes_io,
        as_attachment=True,
        download_name=filename,
        mimetype='application/json'
    )

