import logging
import math
from asyncio.log import logger
import csv
import datetime
from functools import wraps
from threading import Thread
import uuid
from llama_index.llms.openai import OpenAI
from llama_index.core import VectorStoreIndex
from llama_index.core import Settings
from io import BytesIO
import os
import time
from flask import Blueprint,  flash, redirect, render_template, jsonify, render_template_string, request, send_file, session, url_for,current_app, after_this_request, make_response
from src import bcrypt ,socketio 
import json
from llama_index.embeddings.huggingface import HuggingFaceEmbedding 
import urllib.parse
import pandas as pd
import requests
from pathlib import Path
from llama_index.core import StorageContext
from src.backend.tool import load_news_data
from llama_index.core import StorageContext, load_index_from_storage
from .tool import FIELDS, alert_cleanup_task, calculate_stats, convert_to_cytoscape_format, create_news_network, fuzzy_search, generate_id, generate_refutation, get_hot_rumors, get_session_id, handle_image_upload,  load_services_from_csv,  load_user_data, load_user_info, read_evidence, read_submissions, remove_submission, save_conversation,llm, save_user_info, simulate_fake, write_evidence
import random
import string

backend_bp = Blueprint(
    'backend', 
    __name__, 
 template_folder='../templates/backend',     static_folder=os.path.abspath('src/static/backend/website/img'),  # 实际文件路径
    static_url_path='/src/static/backend/website/img'  # URL 前缀
)

# 定义CSV文件路径
USER_DATA_FILE = 'src/static/backend/users.csv'

# 定义用户数据的字段
USER_FIELDS = ['id', 'username', 'password_hash', 'created_at']

def load_services():
    if os.path.exists(SERVICES_FILE):
        with open(SERVICES_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    return []

# 保存服务数据
def save_services(services):
    with open(SERVICES_FILE, 'w', encoding='utf-8') as file:
        json.dump(services, file, ensure_ascii=False, indent=4)

def register_routes(app):
    """将后台蓝图注册到 Flask 应用中"""
    app.register_blueprint(backend_bp, url_prefix='/')

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            # 获取原始请求的URL作为登录后的跳转地址
            next_url = request.url
            return redirect(url_for('backend.login', next=next_url)), 401
        return f(*args, **kwargs)
    return decorated
# 初始化CSV文件（如果不存在）
if not os.path.exists(USER_DATA_FILE):
    pd.DataFrame(columns=USER_FIELDS).to_csv(USER_DATA_FILE, index=False)

@backend_bp.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        # 获取表单数据
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # 检查用户名和密码是否存在
        if not username or not password or not confirm_password:
            flash('用户名、密码和确认密码均为必填项', 'error')
            return redirect(url_for('backend.register'))
        
        # 检查密码和确认密码是否一致
        if password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return redirect(url_for('backend.register'))
        
        # 检查用户名是否已存在
        users_df = pd.read_csv(USER_DATA_FILE)
        if username in users_df['username'].values:
            flash('用户名已存在', 'error')
            return redirect(url_for('backend.register'))
        
        # 哈希密码
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # 生成新用户的数据
        new_user = {
            'id': len(users_df) + 1,
            'username': username,
            'password_hash': password_hash,
            'created_at': pd.Timestamp.now().isoformat()
        }
        
        # 添加新用户到CSV
        users_df = pd.concat(
            [users_df, pd.DataFrame([new_user], columns=users_df.columns)], 
            axis=0, 
            ignore_index=True
        )

        users_df.to_csv(USER_DATA_FILE, index=False)
        
        # 注册成功，跳转到登录页面
        flash('注册成功，请登录', 'success')
        return redirect(url_for('backend.login'))
    
    # GET 请求，渲染注册页面
    return render_template('register.html')



@backend_bp.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # 检查用户名和密码是否存在
        if not username or not password:
            flash('用户名和密码均为必填项', 'error')
            return redirect(url_for('backend.login'))
        
        # 读取用户数据
        users_df = pd.read_csv(USER_DATA_FILE)
        user = users_df[users_df['username'] == username]
        
        # 检查用户名是否存在
        if len(user) == 0:
            flash('用户名不存在', 'error')
            return redirect(url_for('backend.login'))
        
        # 检查密码是否正确
        if not bcrypt.check_password_hash(user['password_hash'].iloc[0], password):
            flash('密码错误', 'error')
            return redirect(url_for('backend.login'))
        
        # 登录成功，设置 session
        session['username'] = username
        session.permanent = True  # 设置为永久会话
        
        # 跳转到指定页面或首页
        next_page = request.args.get('next')
        
        return redirect(next_page or url_for('backend.home'))
    
    # GET 请求，渲染登录页面
    return render_template('login.html')


@backend_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    # 清除会话数据
    session.pop('username', None)
    session.permanent = False  # 取消永久会话
    flash('您已成功退出登录！', 'success')
    return redirect(url_for('backend.login'))


@backend_bp.route('/')
def front_index():
    return render_template('frontend/index.html')

@backend_bp.route('/home')
@login_required
def home():
    return render_template('index.html')

@backend_bp.route('/map')
def map():
    # 添加缓存控制头，设置为1小时
    response = make_response(render_template('map.html'))
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response

@backend_bp.route('/ai_assistant')
def ai_assistant():

    return render_template('ai_assistant.html')

@backend_bp.route('/get_china_data')
def get_china_data():
    # 添加强缓存，因为地图数据一般不会变化
    with open('src/static/backend/china.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    response = jsonify(data)
    response.headers['Cache-Control'] = 'public, max-age=86400'  # 缓存一天
    return response






@backend_bp.route('/graph')
def graph():
    # 读取从 URL 传递的 elements 参数
    elements = request.args.get('elements')
    if elements:
        elements = json.loads(urllib.parse.unquote(elements))  # 解码并解析 JSON 数据
    else:
        elements = []

    return render_template('graph.html', elements=elements)

with open(r'src/static/backend/output_data.json', encoding='utf-8') as f:
    news_data = json.load(f)


@backend_bp.route('/list')
def list_articles():
    # 分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    # 筛选参数
    search_query = request.args.get('q', '').lower()
    platform_filter = request.args.get('platform', '')
    min_credibility = request.args.get('min_credibility', 0, type=float)
    max_credibility = request.args.get('max_credibility', 100, type=float)
    label_filter = request.args.get('label', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    propagation_platform = request.args.get('propagation_platform', '')

    # 筛选数据
    filtered_data = news_data
    if search_query:
        filtered_data = [article for article in filtered_data if
                         search_query in article['title'].lower() or
                         search_query in article['summary'].lower()]
    if platform_filter:
        filtered_data = [article for article in filtered_data if
                        article['platform'] == platform_filter]
    if min_credibility or max_credibility:
        filtered_data = [article for article in filtered_data if
                        min_credibility <= article['credibility']['score'] <= max_credibility]
    if label_filter:
        filtered_data = [article for article in filtered_data if
                        article['label'] == label_filter]
    if start_date and end_date:
        filtered_data = [article for article in filtered_data if
                        start_date <= article['publish_time'] <= end_date]
    if propagation_platform:
        filtered_data = [article for article in filtered_data if
                        any(propagation_platform == item['platform'] for item in article['propagation']['timeline'])]

    # 计算分页
    total = len(filtered_data)
    total_pages = math.ceil(total / per_page)

    # 修正页码范围
    page = max(1, min(page, total_pages))

    # 获取当前页数据
    start = (page - 1) * per_page
    end = start + per_page
    current_articles = filtered_data[start:end]

    # 返回JSON（用于AJAX）或模板渲染
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "articles": current_articles,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_items": total
            }
        })

    return render_template('list.html',
                           articles=current_articles,
                           pagination={
                               "current_page": page,
                               "total_pages": total_pages,
                               "total_items": total
                           })

@backend_bp.route('/platforms')
def get_platforms():
    # 提取所有唯一的平台名称
    platforms = list(set(article['platform'] for article in news_data))
    return jsonify(platforms)
def get_news_by_id(news_id):
    # 根据 news_id 获取具体的新闻内容
    # 这里需要根据实际情况去获取新闻数据，可能是从数据库或文件中
    for article in news_data:
        if article['news_id'] == news_id:
            return article
    return None
@backend_bp.route('/news/<news_id>')
def news_detail(news_id):
    article = get_news_by_id(news_id)

    if article:
        G = create_news_network(article)
    # 转换为 Cytoscape.js 格式
        elements = convert_to_cytoscape_format(G)
        elements_json = json.dumps(elements)
        elements_encoded = urllib.parse.quote(elements_json)  # URL 编码
        return render_template('detail.html', article=article,elements=elements_encoded)
    else:
        print(2)
        return "新闻未找到", 404
@backend_bp.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    try:
        # 获取前端传递过来的反馈数据
        data = request.get_json()
        feedback = data.get('feedback')
        id=data.get('id')

        if not feedback:
            return jsonify({"error": "反馈内容不能为空"}), 400
        
        contribution= load_user_info()
        print('contribution1',contribution)

        username = session['username']
        if "contributions" not in contribution[username]:
            contribution[username]['contributions']=[]
        contribution[username]["contributions"].append({
        "time": datetime.datetime.now().strftime('%Y-%m-%d'),
        "type": '反馈',
        "content": feedback,
        'new_id':id,
        'status':'处理中',
        'status_color':'warning'
    })

        # 保存更新后的收藏数据
        save_user_info(contribution)

      
        return jsonify({"message": "反馈提交成功"}), 200

    except Exception as e:
        print(f"发生错误: {str(e)}")
        return jsonify({"error": "反馈提交失败，请稍后再试"}), 500
@backend_bp.route('/submit_vote', methods=['POST'])
def submit_vote():
    try:
        # 获取前端传递过来的投票结果
        data = request.get_json()
        vote = data.get('vote')
        id=data.get('id')

        if not vote:
            return jsonify({"error": "投票内容不能为空"}), 400
        if vote not in ['agree', 'disagree']:
            return jsonify({"error": "无效的投票选项"}), 400
        contribution= load_user_info()


        username = session['username']
        if "contributions" not in contribution[username]:
            contribution[username]['contributions']=[]
        contribution[username]["contributions"].append({
        "time": datetime.datetime.now().strftime('%Y-%m-%d'),
        "type": '投票',
        "content": vote,
        'new_id':id,
        'status':'处理中',
        'status_color':'warning'
    })

        # 保存更新后的收藏数据
        save_user_info(contribution)
        # 这里可以将投票结果存入数据库或做其他处理
        # 例如：保存到文件、更新数据库等
        # 为了示例，假设我们直接打印投票结果
        print(f"用户投票选项: {vote}")

        return jsonify({"message": "投票成功"}), 200

    except Exception as e:
        print(f"发生错误: {str(e)}")
        return jsonify({"error": "投票提交失败，请稍后再试"}), 500

news_index = None  # 全局索引对象
sessions = {}  # 会话管理
MAX_HISTORY = 5  # 保留最近5轮对话历史

# 初始化 OpenAI 模型
llm = OpenAI(
    temperature=0.1,
    model="gpt-4o-mini",  # 确保模型名称正确
    api_key=os.getenv("OPENAI_API_KEY"),
    api_base='https://api.chatanywhere.tech'  # 自定义 API 端点
)

# 系统提示模板
system_prompt_template = """你是一个专业的虚假新闻检测AI助手，请结合以下三部分信息进行分析：
1. 本地新闻数据库信息（已通过RAG检索相关内容）
2. 当前对话历史
3. 用户的新问题

请按照以下结构组织回答：
【真实性评估】基于数据库内容和事实分析
【传播特征】结合传播时间线、地域分布等数据
【关联信息】相关谣言和知识节点
【建议】给出处理建议

（保持每点分析在100字内，使用emoji图标增强可读性）"""

# 全局设置
Settings.llm = llm  # 设置全局 LLM
Settings.chunk_size = 512  # 优化分块大小
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-zh-v1.5",
    device="cuda"
)

# 初始化新闻索引
INDEX_PERSIST_DIR = Path("src/static/backend/storage")  # 持久化目录
CACHE_TTL = 3600  # 缓存过期时间（秒）
query_cache = {}  # 简单的查询缓存

def initialize_news_index():
    """初始化或加载持久化索引"""
    global news_index
    
    try:
        # 如果存在持久化索引，直接加载
        if INDEX_PERSIST_DIR.exists() and any(INDEX_PERSIST_DIR.iterdir()):
            # 使用缓存机制，避免重复加载
            cache_file = INDEX_PERSIST_DIR / "index_cache.pkl"
            if cache_file.exists():
                import pickle
                import time
                # 检查缓存是否过期（默认24小时）
                cache_time = cache_file.stat().st_mtime
                if time.time() - cache_time < 8640000000000000000:  # 24小时
                    try:
                        with open(cache_file, 'rb') as f:
                            news_index = pickle.load(f)
                            logger.info("从缓存加载新闻索引")
                            return
                    except Exception as cache_error:
                        logger.warning(f"缓存加载失败: {str(cache_error)}")
            
            # 使用并行处理加载索引
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # 异步加载存储上下文
                future = executor.submit(StorageContext.from_defaults, persist_dir=INDEX_PERSIST_DIR)
                storage_context = future.result()
                
                # 异步加载索引
                future = executor.submit(load_index_from_storage, storage_context)
                news_index = future.result()
                
                logger.info("从持久化存储加载新闻索引")
                
                # 保存到缓存
                try:
                    import pickle
                    with open(cache_file, 'wb') as f:
                        pickle.dump(news_index, f)
                except Exception as cache_error:
                    logger.warning(f"缓存保存失败: {str(cache_error)}")
        else:
            # 重新构建索引并持久化
            INDEX_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
            
            # 使用并行处理加载新闻数据
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(load_news_data, "src/static/backend/output_data.json")
                news_docs = future.result()
                
                # 构建索引
                news_index = VectorStoreIndex.from_documents(news_docs)
                
                # 异步持久化
                executor.submit(news_index.storage_context.persist, persist_dir=INDEX_PERSIST_DIR)
                
                logger.info("新闻索引构建完成，已保存到 %s", INDEX_PERSIST_DIR)
        
        logger.info("当前索引包含 %d 条数据", len(news_index.docstore.docs))
    except Exception as e:
        logger.error(f"初始化索引失败: {str(e)}")
        raise

def clean_old_sessions():
    """清理超过24小时未活动的会话"""
    current_time = time.time()
    expired_sessions = []
    
    for session_id, session_data in sessions.items():
        if current_time - session_data.get('last_activity', 0) > 86400:  # 24小时
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        del sessions[session_id]
    
    if expired_sessions:
        logger.info(f"已清理 {len(expired_sessions)} 个过期会话")

# 定期清理会话的任务（可以用定时任务调度器如APScheduler替代）
def schedule_session_cleanup():
    import threading
    clean_old_sessions()
    threading.Timer(3600, schedule_session_cleanup).start()  # 每小时执行一次

@backend_bp.route('/ask', methods=['POST'])
async def ask():
    """处理用户问题并返回AI回答"""
    start_time = time.time()
    user_input = request.json.get('question', '').strip()
    
    if not user_input:
        return jsonify({"error": "问题不能为空"}), 400
        
    logger.info(f"收到用户问题: {user_input[:50]}...")

    # 会话管理
    session_id = session.get('session_id') or str(uuid.uuid4())
    session['session_id'] = session_id

    # 获取或初始化会话上下文
    if session_id not in sessions:
        sessions[session_id] = {
            'history': [],
            'query_engine': news_index.as_query_engine(similarity_top_k=3),
            'last_activity': time.time()
        }
    else:
        sessions[session_id]['last_activity'] = time.time()

    context = sessions[session_id]

    # 检查缓存
    cache_key = f"{session_id}:{user_input}"
    if cache_key in query_cache:
        cache_entry = query_cache[cache_key]
        if time.time() - cache_entry['timestamp'] < CACHE_TTL:
            logger.info(f"从缓存返回结果，耗时: {time.time() - start_time:.2f}秒")
            return jsonify(cache_entry['response'])

    try:
        # 组合查询内容（添加历史上下文）
        history_text = ""
        if context['history']:
            history_text = "\n".join([f"用户: {q}\nAI: {a}" for q, a in context['history'][-MAX_HISTORY:]])
        
        augmented_query = f"""
        对话历史：{history_text}
        新问题：{user_input}
        请结合上述信息回答，如果问题与新闻真实性无关，请礼貌拒绝。
        """

        # 执行 LlamaIndex 查询
        response = await context['query_engine'].aquery(augmented_query)

        # 构建最终回答
        final_answer = response.response
        
        # 更新对话历史
        context['history'].append((user_input, final_answer))
        if len(context['history']) > MAX_HISTORY:
            context['history'].pop(0)

        # 准备返回数据
        result = {
            "answer": final_answer,
            "sources": [{"content": n.node.get_content(), "score": round(n.score, 3)} 
                       for n in response.source_nodes]  # 显示数据来源及相关度
        }
        
        # 保存到缓存
        query_cache[cache_key] = {
            'response': result,
            'timestamp': time.time()
        }
        
        # 清理过大的缓存
        if len(query_cache) > 1000:
            # 删除最旧的20%缓存
            sorted_cache = sorted(query_cache.items(), key=lambda x: x[1]['timestamp'])
            for k, _ in sorted_cache[:200]:
                del query_cache[k]

        # 保存到数据库（示例函数）
        try:
            save_conversation(session_id, user_input, final_answer)
        except Exception as db_error:
            logger.error(f"保存对话到数据库失败: {str(db_error)}")
            # 继续处理，不影响用户体验

        logger.info(f"处理完成，耗时: {time.time() - start_time:.2f}秒")
        return jsonify(result)

    except Exception as e:
        logger.error(f"查询失败：{str(e)}", exc_info=True)
        return jsonify({
            "error": "分析失败，请稍后重试",
            "details": str(e)
        }), 500

# 健康检查端点
@backend_bp.route('/health', methods=['GET'])
def health_check():
    """API健康检查"""
    if news_index is None:
        return jsonify({"status": "error", "message": "索引未初始化"}), 503
    
    return jsonify({
        "status": "ok",
        "index_size": len(news_index.docstore.docs),
        "active_sessions": len(sessions)
    })

# 初始化
initialize_news_index()
schedule_session_cleanup()  # 启动会话清理任务

@backend_bp.route('/report')

def report():
    return render_template('report.html',user=session['username'])  # 渲染举报页面


@backend_bp.route('/report_submit')
def report_submit():
    return render_template('report_submit.html')  # 渲染举报页面




@backend_bp.route('/report_crowdfunding_dashboard')
def report_crowdfunding_dashboard():
    return render_template('crowdfunding_dashboard.html') 

@backend_bp.route('/api/evidence', methods=['GET', 'POST'])
def handle_evidence():
    if request.method == 'POST':
        # 添加新证据
        new_data = request.json
        data = read_evidence()
        
        new_entry = {
            'id': generate_id(),
            'title': new_data.get('title', ''),
            'content': new_data.get('content', ''),
            'category': new_data.get('category', '其他'),
            'source': new_data.get('source', '未知来源'),
            'timestamp': datetime.datetime.now().isoformat(),
            'related_case': new_data.get('related_case', ''),
            'file_type': new_data.get('file_type', '')
        }
        
        
        if not all(new_entry.values()):
            return jsonify({"success": False, "message": "所有字段均为必填项"}), 400

    # 保存到CSV
        try:
            contribution= load_user_info()
            print('contribution1',contribution)

            username = session['username']

            if "contributions" not in contribution[username]:
                contribution[username]['contributions']=[]

            contribution[username]["contributions"].append({

                "time": datetime.datetime.now().strftime('%Y-%m-%d'),
                "type": '众筹验证',
                "content": new_entry['content'],
                'evidence_id':new_entry['id'],
                'status':'处理中',
                'status_color':'warning'
        })

            # 保存更新后的收藏数据
            save_user_info(contribution)
            data.append(new_entry)
            write_evidence(data)
            return jsonify({"success": True, "message": "证据已成功保存"})
        except Exception as e:
            return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500
    
    # 获取证据数据
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    data = read_evidence()
    
    # 过滤数据
    filtered = []
    for row in data:
        if search.lower() not in row['content'].lower():
            continue
        if category and row['category'] != category:
            continue
        filtered.append(row)
    
    # 按时间排序
    filtered.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify(filtered)

@backend_bp.route('/export')
def export_data():
    # 读取CSV数据
    data = read_evidence()
    
    # 写入临时文件（UTF-8 with BOM）
    # 使用绝对路径创建临时文件
    temp_dir = os.path.dirname(os.path.abspath(__file__))
    temp_file = os.path.join(temp_dir, 'temp_evidence.csv')
    
    with open(temp_file, 'w', newline='', encoding='utf-8-sig') as f:  # 使用 utf-8-sig
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(data)
    
    # 发送文件但不立即删除
    # 注册一个删除函数，在请求结束后执行
    @after_this_request
    def remove_file(response):
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception as e:
            print(f"删除临时文件出错: {e}")
        return response
        
    return send_file(
        temp_file,
        mimetype='text/csv',
        as_attachment=True,
        download_name='evidence_export.csv'
    )

@backend_bp.route('/report_leaderboard')
def report_leaderboard():
    return render_template('leaderboard.html') 
@backend_bp.route('/leaderboard')
def leaderboard():
    leaderboard_data = {
        "leaderboard": [
            {"name": "用户A", "score": 500, "avatar": "https://randomuser.me/api/portraits/men/1.jpg", "rank_change": "+10", "last_updated": "2025-02-20", "status": "在线", "country": "中国"},
            {"name": "用户B", "score": 400, "avatar": "https://randomuser.me/api/portraits/women/2.jpg", "rank_change": "-2", "last_updated": "2025-02-19", "status": "离线", "country": "美国"},
            {"name": "用户C", "score": 300, "avatar": "https://randomuser.me/api/portraits/men/2.jpg", "rank_change": "0", "last_updated": "2025-02-18", "status": "在线", "country": "英国"},
            {"name": "用户D", "score": 250, "avatar": "https://randomuser.me/api/portraits/men/3.jpg", "rank_change": "+5", "last_updated": "2025-02-21", "status": "在线", "country": "印度"},
            {"name": "用户E", "score": 220, "avatar": "https://randomuser.me/api/portraits/women/3.jpg", "rank_change": "-3", "last_updated": "2025-02-15", "status": "离线", "country": "巴西"},
            {"name": "用户F", "score": 180, "avatar": "https://randomuser.me/api/portraits/men/4.jpg", "rank_change": "+7", "last_updated": "2025-02-19", "status": "在线", "country": "日本"},
            {"name": "用户G", "score": 160, "avatar": "https://randomuser.me/api/portraits/women/4.jpg", "rank_change": "+12", "last_updated": "2025-02-18", "status": "在线", "country": "法国"},
            {"name": "用户H", "score": 140, "avatar": "https://randomuser.me/api/portraits/men/5.jpg", "rank_change": "-1", "last_updated": "2025-02-17", "status": "离线", "country": "德国"}
        ]
    }
    return jsonify(leaderboard_data)

@backend_bp.route('/report_discussion_forum')
def report_discussion_forum():
    return render_template('discussion_forum.html') 


message_history = []
@socketio.on('new_message')
def handle_new_message(data):
    # 广播消息给所有客户端
    socketio.emit('message_received', {
        'author': session['username'],
        'content': data['content'],
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    # 存储到内存（可选）
    message_history.append(data)

services = []
SERVICES_FILE = 'src/static/backend/website/services.json'



@backend_bp.route('/tp', methods=['GET', 'POST'])
def tp():
    services = load_services()
    print(services)
    services2 = load_services_from_csv()
    
    if request.method == 'POST':
        img_url = request.form.get('img_url', '')
        description = request.form.get('description', '').strip()
        url = request.form.get('url', '').strip()
        
        if not all([description, url]):
            flash('描述和链接不能为空！')
            return redirect(url_for('backend.tp'))
        
        img_file = request.files.get('img_upload')
        img_path = handle_image_upload(img_file)
        print(img_path)

        if img_path:
            img_url = url_for('backend.static', filename=img_path)
        
        new_service = {
            'img': img_url,
            'description': description,
            'url': url
        }
        
        # 检查是否存在重复的服务
        is_duplicate = False
        # 检查services列表
        for service in services:
            if service['description'] == description and service['url'] == url:
                is_duplicate = True
                break
        # 如果没有在services中找到重复，继续检查services2
        if not is_duplicate:
            for service in services2:
                if service['description'] == description and service['url'] == url:
                    is_duplicate = True
                    break
        
        if is_duplicate:
            flash('该服务已经存在！')
            return redirect(url_for('backend.tp'))
        
        services.append(new_service)
        save_services(services)
        return redirect(url_for('backend.tp'))
    
    combined_services = services + services2
    return render_template('tp.html', services=combined_services,user= session['username'])
@backend_bp.route('/add_to_favorites', methods=['POST'])
def add_to_favorites():


    data = request.get_json()
    print('data1',data)
    news_id = data.get('id')
    title = data.get('title')
    description = data.get('description')
    content=data.get('content')
    date = data.get('date')
    if not title:
        title='无'
    if not content:
        content='无'
    if not description:
        description=content
    if not all([news_id, title, description, date]):
        return jsonify({'success': False, 'message': '缺少必要参数'}), 400
    
    # 加载现有的收藏数据
    favorites_data = load_user_info()
    print('data',favorites_data)
    # 获取当前用户的收藏列表
    username = session['username']
    if username not in favorites_data:
        favorites_data[username] = {"favorites": []}

    # 检查是否已经收藏过
    if any(item['id'] == news_id for item in favorites_data[username]["favorites"]):
        return jsonify({'success': False, 'message': '已收藏过该新闻'}), 400

    # 添加新的收藏
    favorites_data[username]["favorites"].append({
        "title": title,
        "description": description,
        "date": date,
        "id": news_id
    })

    # 保存更新后的收藏数据
    save_user_info(favorites_data)

    return jsonify({'success': True, 'message': '已成功加入收藏'})

@backend_bp.route('/remove_from_favorites', methods=['POST'])
def remove_from_favorites():


    data = request.get_json()
    news_id = data.get('id')

    if not news_id:
        return jsonify({'success': False, 'message': '缺少新闻ID'}), 400

    # 加载现有的收藏数据
    favorites_data = load_user_info()

    # 获取当前用户的收藏列表
    username = session['username']
    if username not in favorites_data:
        return jsonify({'success': False, 'message': '用户没有收藏记录'}), 404

    # 移除指定的新闻
    user_favorites = favorites_data[username]["favorites"]
    initial_length = len(user_favorites)
    favorites_data[username]["favorites"] = [item for item in user_favorites if item['id'] != news_id]

    # 如果没有移除任何新闻，说明新闻不存在于收藏列表中
    if len(favorites_data[username]["favorites"]) == initial_length:
        return jsonify({'success': False, 'message': '新闻不在收藏列表中'}), 404

    # 保存更新后的收藏数据
    save_user_info(favorites_data)

    return jsonify({'success': True, 'message': '已成功移除收藏'})

@backend_bp.route("/profile")
def profile():

    user_name=session['username']
    user_data = load_user_data(user_name)
    if not user_data:
        user_data={}
    user_data['username'] = user_name  # 确保username被传递给模板
    return render_template("profile.html", **user_data)


@backend_bp.route('/edu')
def edu():
    return render_template('edu.html')  # 渲染举报页面
@backend_bp.route('/sandbox')
def sandbox():
    return render_template('sandbox.html')

@backend_bp.route('/submit-test', methods=['POST'])
def submit_test():
    # 获取表单数据
    answer = request.form.get('question1')
    response = {'message': '答案提交成功', 'answer': answer}
    return jsonify(response)


with open(r'src/static/backend/test/stages.json', encoding='utf-8') as f:
    stages = json.load(f)


with open(r'src/static/backend/test/cases.json', encoding='utf-8') as f:
    cases = json.load(f)


with open(r'src/static/backend/test/tests.json', encoding='utf-8') as f:
    tests = json.load(f)

@backend_bp.route('/api/stage/<int:stage_number>')
def get_stage(stage_number):
    stage = next((s for s in stages if s["number"] == stage_number), None)
    if not stage:
        return jsonify({"error": "Stage not found"}), 404
    return jsonify(stage)

@backend_bp.route('/api/case/<int:case_id>')
def get_case(case_id):
    case = next((c for c in cases if c["id"] == case_id), None)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    return jsonify(case)

@backend_bp.route('/api/test')
def get_test():
    import random
    test = random.choice(tests)
    return jsonify({
        "id": test["id"],
        "content": test["content"]
    })

@backend_bp.route('/api/submit_test', methods=['POST'])
def submit():
    data = request.get_json()
    answer = data.get('answer', None)
    if not answer:
        return jsonify({"error": "Missing answer"}), 400
    print(data.get('test_id'))
    test = next((t for t in tests if t["id"] == data.get('test_id')), None)
    print(test)
    if not test:
        return jsonify({"error": "Test not found"}), 404
    
    correct = answer.lower() == test.get('correctAnswer', '').lower()
    print(correct)
    return jsonify({
        "correct": correct,
        "correctAnswer": test.get('correctAnswer', '')
    })

correct_answers = {
    'question1': 'option2',
    'question2': 'option2',
    'question3': 'option2',
    'question4': 'option1',
    'question5': 'option3',
    'question6': 'option2',
    'question7': 'option3',
    'question8': 'option2',
    'question9': 'option2',
    'question10': 'option2',
}

@backend_bp.route('/question')
def question():
    try:
        file_path = os.path.join('src/templates/backend', 'question.html')
        with open(file_path, encoding='UTF-8') as f:
            template_content = f.read()
            return render_template_string(template_content)
    except Exception as e:
        return f"Error loading template: {e}", 500
@backend_bp.route('/submit_answer', methods=['POST'])
def submit_answer():
    # 获取用户提交的答案
    user_answers = {
        'question1': request.form.get('question1'),
        'question2': request.form.get('question2'),
        'question3': request.form.get('question3'),
        'question4': request.form.get('question4'),
        'question5': request.form.get('question5'),
        'question6': request.form.get('question6'),
        'question7': request.form.get('question7'),
        'question8': request.form.get('question8'),
        'question9': request.form.get('question9'),
        'question10': request.form.get('question10'),
    }

    # 计算得分
    score = 0
    total_questions = len(correct_answers)
    for question, correct_answer in correct_answers.items():
        if user_answers.get(question) == correct_answer:
            score += 1

    # 计算正确率
    accuracy = (score / total_questions) * 100

    # 根据得分评级
    if score >= 9:
        evaluation = "优秀！您对虚假新闻的识别能力非常强。"
    elif score >= 6:
        evaluation = "良好！您能够识别大部分虚假新闻，但仍需提高。"
    else:
        evaluation = "需加强！您需要进一步学习和练习以识别虚假新闻。"

    # 返回结果以供JavaScript处理
    return jsonify({
        'score': score,
        'total_questions': total_questions,
        'accuracy': round(accuracy, 2),
        'evaluation': evaluation
   })



with open(r'src/static/backend/new_data/new_data.json', encoding='utf-8') as f:
    fake_news_data = json.load(f)

@backend_bp.route('/new_data')
def new_data():
    return render_template('new_data.html')

@backend_bp.route('/get_new_data')
def get_new_data():
    return jsonify(fake_news_data)







@backend_bp.route('/dashboard')
def dashboard():
    # 加载数据

    
    # 计算24小时传播量
    top_news = []
    current_time = datetime.datetime.now()
    print('new_data',news_data)
    for news in news_data:
        # 过滤没有传播数据的条目
        if 'propagation' not in news:
            continue
            
        total_shares = 0
        for timeline in news['propagation']['timeline']:
            # 解析时间戳（根据你的实际时间格式调整）
            timestamp = datetime.datetime.fromisoformat(timeline['timestamp'].replace("Z", "+00:00"))
            
            # 计算时间差
            time_diff = current_time - timestamp
            if time_diff <= datetime.timedelta(days=1825):
                total_shares += timeline.get('shares', 0)
        
        # 只保留有传播量的新闻
        if total_shares > 0:
            top_news.append({
                'title': news['title'] or news['content'][:30] + "...",  # 使用内容前30字作为标题
                'shares': total_shares,
                'news_id': news['news_id']
            })
    
    # 按传播量排序并取前
    top_news = sorted(top_news, key=lambda x: x['shares'], reverse=True)[:6]
    print(top_news)
    return render_template('dashboard.html', top_news=top_news)
@backend_bp.route('/statistic')
def statistic():
    stats = calculate_stats(news_data)
    return render_template('statistic.html', stats=stats)

@backend_bp.route('/hotpot')
def hotpot():
    hot_rumors = get_hot_rumors(news_data)
    return render_template('hotpot.html', hot_rumors=hot_rumors)

@backend_bp.route('/get_map_data')
def get_map_data():
    # 添加缓存控制头
    response = jsonify(news_data)
    response.headers['Cache-Control'] = 'public, max-age=3600'  # 缓存1小时
    return response


@backend_bp.route('/province/<province_name>')
def show_province(province_name):
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    
    # 这里假设你有不同省份的数据
    # 可以根据实际情况过滤 JSON 数据
    filtered_data = [news for news in news_data if news['location'] == province_name]
    
    # 计算总页数和分页数据
    total_items = len(filtered_data)
    total_pages = (total_items + per_page - 1) // per_page  # 向上取整
    
    # 确保页码在有效范围内
    if page < 1:
        page = 1
    if page > total_pages and total_pages > 0:
        page = total_pages
    
    # 获取当前页的数据
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_items)
    current_page_data = filtered_data[start_idx:end_idx] if filtered_data else []
    
    if filtered_data:
        return render_template('province_data.html', 
                              data=current_page_data, 
                              total_items=total_items,
                              current_page=page,
                              per_page=per_page,
                              total_pages=total_pages,
                              province_name=province_name,
                              max=max,
                              min=min)  # 添加min函数到模板上下文
    else:
        return render_template('province_data.html', 
                              data=None, 
                              total_items=0,
                              current_page=1,
                              per_page=per_page,
                              total_pages=0,
                              province_name=province_name,
                              max=max,
                              min=min)  # 添加min函数到模板上下文
@backend_bp.route('/proxy-image')
def proxy_image():
    url = request.args.get('url')
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    'Referer': 'https://weibo.com',  # 根据实际情况调整
}



    # 去掉单引号和方括号
    url = url.replace("'", "").strip("[]")
    if not url:
        return '图片URL不能为空', 400
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        img = BytesIO(response.content)
        return send_file(img, mimetype=response.headers['Content-Type'])
    except requests.exceptions.RequestException as e:
        return f'获取图片失败：{e}', 500
    


@backend_bp.route('/rumor')
def rumor():
    return render_template('rumor.html')

@backend_bp.route('/generate_refutation', methods=['POST'])
async def generate_refutation_endpoint():
    data = request.get_json()
    rumor = data.get('rumor', '')
    if rumor:
        refutation = await generate_refutation(rumor)
        return jsonify({"refutation": refutation})
    return jsonify({"refutation": "没有提供谣言内容"})

@backend_bp.route('/simulate_fake', methods=['POST'])
async def simulate_fake_endpoint():
    data = request.get_json()
    parameters = data.get('parameters', '')
    if parameters:
        simulated_content = await simulate_fake(parameters)
        print(simulated_content)
        return jsonify({"simulatedContent": simulated_content})
    return jsonify({"simulatedContent": "没有提供参数"})



# Function to perform fuzzy search


@backend_bp.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '')
    if query:
        results = fuzzy_search(query, news_data)
        
        return jsonify(results)
    return jsonify([])





@backend_bp.route('/review_page')
def admin_dashboard():
    """管理员审核界面"""
    submissions = read_submissions()
    return render_template('admin.html', submissions=submissions)

@backend_bp.route('/review', methods=['POST'])
def handle_review():
    """处理审核操作"""
    submission_id = request.form.get('id')
    action = request.form.get('action')
    reason = request.form.get('reason', '')  # 获取操作原因，默认为空字符串

    if not submission_id or not action:
        flash('操作失败：缺少必要参数', 'error')
        return redirect(url_for('backend.admin_dashboard'))

    # 根据不同操作类型处理
    if action == 'approve':
        # 同意操作，记录原因（如果有）
        approve_submission(submission_id, reason)
        flash('内容已通过审核', 'success')
    elif action == 'reject':
        # 删除操作，记录删除原因
        remove_submission(submission_id, reason)
        flash('内容已被删除', 'success')
    elif action == 'pending':
        # 暂缓处理操作，记录暂缓原因
        mark_submission_pending(submission_id, reason)
        flash('内容已标记为暂缓处理', 'success')
    else:
        flash('未知的操作类型', 'error')

    return redirect(url_for('backend.admin_dashboard'))

# 处理审核通过的函数
def approve_submission(submission_id, reason=''):
    """标记提交内容为已通过，并记录原因"""
    # 这里可以添加将内容标记为已通过的逻辑
    # 例如更新数据库中的状态字段，记录审核原因等
    # 目前仅保留记录，不做任何操作
    print(f"内容ID {submission_id} 已通过审核，原因：{reason}")
    return True

# 处理删除内容的函数
def remove_submission(submission_id, reason=''):
    """删除提交内容，并记录删除原因"""
    # 这里可以添加记录删除原因的逻辑
    print(f"内容ID {submission_id} 已被删除，原因：{reason}")
    # 实际删除逻辑（原有功能）
    # 可以在这里添加将删除原因写入日志的代码
    return True

# 处理暂缓内容的函数
def mark_submission_pending(submission_id, reason):
    """标记提交内容为暂缓处理，并记录原因"""
    # 这里可以添加将内容标记为暂缓处理的逻辑
    # 例如更新数据库中的状态字段，记录暂缓原因等
    print(f"内容ID {submission_id} 已标记为暂缓处理，原因：{reason}")
    return True

alerts_db = {
    "news_plf01A00001": {
        "message": "地震预测不实信息",
        "start_time": time.time(),  # 添加警报开始时间
        "duration": 195             # 总持续时间195秒
    }
}

Thread(target=alert_cleanup_task, daemon=True).start()

@backend_bp.route('/api/active-alert', methods=['GET'])
def get_active_alert():
    if alerts_db:
        alert_id, alert = next(iter(alerts_db.items()))
        elapsed = time.time() - alert["start_time"]
        remaining = max(alert["duration"] - int(elapsed), 0)
        return jsonify({
            "id": alert_id,
            "remaining_time": remaining
        })
    return jsonify({"error": "没有活跃警报"}), 404

@backend_bp.route('/api/alerts/<alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    if alert_id in alerts_db:
        del alerts_db[alert_id]
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "警报不存在"}), 404

@backend_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        # 获取表单数据
        action = request.form.get('action', '')
        
        # 第一步：验证身份
        if action == 'verify':
            username = request.form.get('username')
            verification_code = request.form.get('verification_code')
            
            # 检查用户名是否存在
            users_df = pd.read_csv(USER_DATA_FILE)
            user = users_df[users_df['username'] == username]
            
            if len(user) == 0:
                flash('用户名不存在', 'error')
                return redirect(url_for('backend.forgot_password'))
            
            # 验证验证码
            # 这里应该从会话或数据库中获取之前发送的验证码
            # 为了演示，我们假设验证码是 "123456"
            if verification_code != session.get('verification_code'):
                flash('验证码错误', 'error')
                return redirect(url_for('backend.forgot_password'))
            
            # 验证成功，将用户名存入会话
            session['reset_username'] = username
            flash('身份验证成功，请设置新密码', 'success')
            return redirect(url_for('backend.forgot_password', step=2))
        
        # 第二步：重置密码
        elif action == 'reset':
            username = session.get('reset_username')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not username:
                flash('请先验证身份', 'error')
                return redirect(url_for('backend.forgot_password'))
            
            if not new_password or not confirm_password:
                flash('密码和确认密码均为必填项', 'error')
                return redirect(url_for('backend.forgot_password', step=2))
            
            if new_password != confirm_password:
                flash('两次输入的密码不一致', 'error')
                return redirect(url_for('backend.forgot_password', step=2))
            
            # 更新密码
            users_df = pd.read_csv(USER_DATA_FILE)
            user_index = users_df[users_df['username'] == username].index[0]
            
            # 哈希新密码
            password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
            
            # 更新密码哈希
            users_df.at[user_index, 'password_hash'] = password_hash
            users_df.to_csv(USER_DATA_FILE, index=False)
            
            # 清除会话中的重置信息
            session.pop('reset_username', None)
            session.pop('verification_code', None)
            
            flash('密码重置成功，请使用新密码登录', 'success')
            return redirect(url_for('backend.forgot_password', step=3))
    
    # GET 请求，渲染忘记密码页面
    step = request.args.get('step', 1)
    try:
        step = int(step)
    except ValueError:
        step = 1
    
    return render_template('forgot_password.html', step=step)

@backend_bp.route('/send-verification-code', methods=['POST'])
def send_verification_code():
    username = request.form.get('username')
    
    if not username:
        return jsonify({'success': False, 'message': '请输入用户名'})
    
    # 检查用户名是否存在
    users_df = pd.read_csv(USER_DATA_FILE)
    user = users_df[users_df['username'] == username]
    
    if len(user) == 0:
        return jsonify({'success': False, 'message': '用户名不存在'})
    
    # 生成6位随机验证码
    verification_code = ''.join(random.choices(string.digits, k=6))
    
    # 将验证码存入会话
    session['verification_code'] = verification_code
    
    # 在实际应用中，这里应该发送验证码到用户的邮箱或手机
    # 为了演示，我们只是将验证码返回给前端
    return jsonify({
        'success': True, 
        'message': '验证码已发送',
        'code': verification_code  # 注意：实际应用中不应该返回验证码
    })


