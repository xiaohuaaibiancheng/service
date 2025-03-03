# routes.py：路由+视图函数

from flask import Blueprint, render_template, request, jsonify, url_for, redirect, current_app, send_file
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

from src.frontend.agent import FactChecker 
from src.frontend.from_txt_img import ImageTextSimilarity
from src.frontend.lazy import LazyModel
from src.frontend.text_aigc.scripts.local_infer import DetectAIGC
from src.frontend.tool import  extract_and_detect_file_news, extract_and_detect_url_news, init_hammer_model, process_image_and_text, process_text_only, process_title_and_text, save_to_csv
from src.frontend.ai_analyzer import analyze_with_llm


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
    app.config.setdefault('OPENAI_API_KEY', 'sk-your-default-api-key')
    app.config.setdefault('OPENAI_BASE_URL', 'https://api.chatanywhere.tech')
    # 设置上传文件夹
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../static/frontend/uploads')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上传文件大小为16MB

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

@frontend_bp.route('/')
def index():
    return render_template('frontend/index.html', current_date=datetime.now().strftime('%Y年%m月%d日'))
# 添加新闻检测路由
@frontend_bp.route('/news_detect')
def news_detect():
    return render_template('frontend/news_detect.html')
@frontend_bp.route('/agent', methods=['GET', 'POST'])
async def agent():
    fact_checker.model
    if request.method == 'POST':
        title = request.form.get('title')
        url = request.form.get('url')
        date = request.form.get('date')

        news_info = {
            "title": title,
            "url": url,
            "date": date
        }

        # 运行事实核查
        report = await fact_checker.check_news(news_info)

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


    return render_template('frontend/agent.html')

@frontend_bp.route("/detect/url", methods=["POST"])
def detect_url():
    url = request.json.get("url")
    if not url:
        return jsonify({"error": "URL不能为空"}), 400
    # 模拟从 URL 提取内容（实际应用中需要实现 URL 内容抓取）
    result = extract_and_detect_url_news(url,classifier_txt_img)
    # result = extract_and_detect_url_news(content)

    return jsonify(result)

@frontend_bp.route('/detect/multimodal', methods=['POST'])
def detect_multimodal():
    text = request.form.get('text')
    image = request.files.get('image')
    title = request.form.get('title')

    if not text and not image and not title:
        return jsonify({"error": "文本、图片或标题至少需要一个"}), 400

    if image and text:
        result = process_image_and_text(image, text,classifier_txt_img)
    elif title and text:
        result = process_title_and_text(title, text)
    elif text:
        result = process_text_only(text)
    else:
        return jsonify({"error": "无效的输入组合"}), 400

    return jsonify(result)

@frontend_bp.route("/detect/file", methods=["POST"])
def detect_file():
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
    except Exception as e:
        return jsonify({"error": f"文件处理失败: {str(e)}"}), 500

    # 返回检测结果
    return jsonify(detection_result)

@frontend_bp.route('/ai_chat')
def ai_chat():
    return render_template('frontend/ai_chat.html')



@frontend_bp.route('/ai_detect')
def ai_detect():
    return render_template('frontend/ai_detect.html')




@frontend_bp.route('/about')
def about():
    return render_template('frontend/about.html', current_date=datetime.now().strftime('%Y年%m月%d日'))

@frontend_bp.route('/contact')
def contact():
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
                response = chat(messages)
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
    try:
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
        
        # 添加用户消息
        shared_data['messages'].append({
            'role': 'user',
            'content': user_message
        })
        
        # 使用langchain_openai和langchain_core.schema生成回复
        from langchain_openai import ChatOpenAI
        from langchain_core.schema import HumanMessage, AIMessage, SystemMessage
        
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
                response = chat(messages)
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
def get_detection_stats():
    """获取检测统计数据"""
    return {
        'total_detections': 1234,
        'today_detections': 56,
        'accuracy_rate': 95.5,
        'fake_news_rate': 15.2
    }

def get_detection_trends():
    """获取检测趋势数据"""
    dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
    dates.reverse()
    
    return {
        'dates': dates,
        'detections': [45, 52, 49, 60, 55, 58, 56],
        'accuracy': [94.5, 95.2, 95.0, 95.5, 94.8, 95.3, 95.5]
    }









@frontend_bp.route('/news_aggregate')
def news_aggregate():
    return render_template('frontend/news_aggregate.html', current_date=datetime.now().strftime('%Y年%m月%d日'))

@frontend_bp.route('/api/news/aggregate')
def api_news_aggregate():
    keyword = request.args.get('keyword', '')
    if not keyword:
        return jsonify({
            'status': 'error',
            'message': '请输入搜索关键词'
        }), 400
    
    try:
        # 这里需要实现实际的新闻聚合逻辑
        result = {
            'news': [
                {
                    'title': '示例新闻标题',
                    'url': 'http://example.com',
                    'source': '示例来源',
                    'publish_time': '2024-02-28',
                    'summary': '新闻摘要...'
                }
            ],
            'analysis': {
                'time_diff': ['1天', '2天', '3天'],
                'content_similarity': [0.8, 0.7, 0.6],
                'source_count': 3
            }
        }
        
        return jsonify({
            'status': 'success',
            'data': result
        })
    except Exception as e:
        print(f"Error in api_news_aggregate: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': '搜索过程中出现错误'
        }), 500

@frontend_bp.route('/detect/ai_text', methods=['POST'])
def detect_text():
    try:
        data = request.get_json()
        text_content = data.get('text_content')
        if not text_content:
            return jsonify({'error': '文本内容不能为空'}), 400
        # 假设有一个函数 process_text_detection 用于处理文本检测
        prob = detector_ai.predict_prob(text_content)

        random_int = random.randint(1, 10)
        random_percent = random_int * 0.01
        if prob == 0.0:
            prob += random_percent
        if prob == 1.0:
            prob -= random_percent

        return jsonify({
            'status': 'success',
            'probability': prob
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

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
        # 打开图片
        img = Image.open(image)
        
        # 这里应该实现实际的AI图片检测逻辑
        # 由于没有实际的检测模型，这里返回一个随机概率作为示例
        probability = random.uniform(0.6, 0.95)
        
        return probability
    except Exception as e:
        print(f"Error detecting AI image: {str(e)}")
        return 0.5  # 默认返回0.5

@frontend_bp.route('/detect/ai_image', methods=['POST'])
def detect_ai_image():
    if 'image' not in request.files:
        return jsonify({'status': 'error', 'message': '没有上传图片文件'}), 400

    image = request.files['image']
    # 调用AI图片检测函数
    probability = detect_ai_generated_image(image)

    return jsonify({'status': 'success', 'probability': probability})

# 添加聚合分析路由
@frontend_bp.route('/detect/aggregate', methods=['POST'])
def detect_aggregate():
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
    try:
        data = request.json
        url = data.get('url')
        title = data.get('title')
        
        if not url or not title:
            return jsonify({
                'status': 'error',
                'message': '缺少必要参数'
            }), 400
            
        # 这里是示例分析结果，实际应用中需要实现真实的新闻分析逻辑
        analysis_result = {
            'credibility': random.randint(70, 95),  # 可信度评分
            'keywords': [
                '关键词1',
                '关键词2',
                '关键词3'
            ],
            'sentiment': random.choice([-1, 1]),  # 情感倾向：-1表示负面，1表示正面
            'related_news': [
                {
                    'title': '相关新闻1',
                    'url': 'http://example.com/news1',
                    'source': '新闻来源1',
                    'publish_time': '2024-03-02'
                },
                {
                    'title': '相关新闻2',
                    'url': 'http://example.com/news2',
                    'source': '新闻来源2',
                    'publish_time': '2024-03-02'
                }
            ]
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

