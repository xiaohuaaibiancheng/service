import csv
import datetime
from functools import wraps
import json
import os
from pathlib import Path
import random
import time
from typing import Dict, List
import pandas as pd
from werkzeug.utils import secure_filename
from langchain_openai import ChatOpenAI
import openai
from openai import OpenAI
from flask import current_app
import networkx as nx
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL

INDEX_PERSIST_DIR=Path("src/static/backend/storage") 
llm = ChatOpenAI(
    api_key=OPENAI_API_KEY,
    model_name="gpt-4o-mini",
    base_url=OPENAI_BASE_URL,
    temperature=0.7
)

def create_news_network(news):
    """
    创建一个新闻传播图谱，结合 knowledge_nodes 表示新闻关系节点
    :param news: 单个新闻对象（字典）
    :return: NetworkX 图对象
    """
    G = nx.DiGraph()  # 使用有向图

    # 添加新闻节点
    news_id = news["news_id"]
    G.add_node(news_id, label=f"新闻: {news['title']}", type="news", platform=news["platform"], publish_time=news["publish_time"])

    # 添加知识节点并连接新闻节点
    for knowledge in news["relations"]["knowledge_nodes"]:
        G.add_node(knowledge, label=f"知识: {knowledge}", type="knowledge")
        G.add_edge(news_id, knowledge, label="关联知识")

    # 添加传播路径（假设传播路径在 propagation 中定义）
    for timeline in news["propagation"]["timeline"]:
        platform = timeline["platform"]
        G.add_node(platform, label=f"平台: {platform}", type="platform")
        G.add_edge(news_id, platform, label="传播路径")

    return G

def convert_to_cytoscape_format(graph):
    """
    将 NetworkX 图转换为 Cytoscape.js 格式，支持节点和边的所有属性。

    :param graph: NetworkX 图对象
    :return: Cytoscape.js 格式的元素列表
    """
    elements = []

    # 添加节点
    for node in graph.nodes:
        node_data = {"id": node, "label": graph.nodes[node].get("label", node)}
        # 添加节点的其他属性
        for key, value in graph.nodes[node].items():
            if key != "label":  # 避免覆盖 label
                node_data[key] = value
        elements.append({"data": node_data})

    # 添加边
    for edge in graph.edges:
        source, target = edge
        edge_data = {
            "id": f"{source}-{target}",  # 生成唯一 ID
            "source": source,
            "target": target,
            "label": graph.edges[edge].get("label", ""),  # 默认空字符串
        }
        # 添加边的其他属性
        for key, value in graph.edges[edge].items():
            if key != "label":  # 避免覆盖 label
                edge_data[key] = value
        elements.append({"data": edge_data})

    return elements
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
def load_services_from_csv():
    csv_path = 'src/static/backend/website/web.csv'
    data = pd.read_csv(csv_path)
    return data.to_dict(orient='records')
# 处理用户上传的图标和数据
def handle_image_upload(image_file):
    if image_file and allowed_file(image_file.filename):
        filename = secure_filename(image_file.filename)
        filepath = os.path.join(current_app.config['IMG_FOLDER'], filename)
        image_file.save(filepath)
        # 返回相对于 static_folder 的路径
        return filename  # 只返回文件名，不包含完整路径
    return None

from llama_index.core.schema import Document
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# 加载服务数据
def load_news_data(file_path: Path) -> List[Document]:
    """加载并解析新闻数据"""
    documents = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            news_list = json.load(f)
            for news in news_list:
                # 构建结构化文本
                text_parts = [
                    f"新闻 ID：{news['news_id']}",
                    f"标题：{news['title']}",
                    f"发布时间：{news['publish_time']}",
                    f"平台：{news['platform']}",
                    f"标签：{news['label']}",
                    f"可信度评分：{news['credibility']['score']}",
                    "可信度维度评分："
                    f"- 来源可信度：{news['credibility']['dimension_scores']['source']}",
                    f"- 内容可信度：{news['credibility']['dimension_scores']['content']}",
                    f"- 逻辑合理性：{news['credibility']['dimension_scores']['logic']}",
                    "\n传播情况："
                ]

                # 处理传播时间线
                for timeline in news['propagation']['timeline']:
                    text_parts.append(
                        f"{timeline['timestamp']} 在 {timeline['platform']} 平台传播，"
                        f"分享 {timeline['shares']} 次，地区分布：{', '.join([f'{k}({v})' for k, v in timeline['geo_distribution'].items()])}"
                    )

                # 添加用户画像
                text_parts.extend([
                    "\n用户画像：",
                    f"年龄分布：{json.dumps(news['propagation']['user_profile']['age_dist'], ensure_ascii=False)}",
                    f"设备比例：{json.dumps(news['propagation']['user_profile']['device_ratio'], ensure_ascii=False)}"
                ])

                # 添加关联信息
                if news['relations']:
                    text_parts.extend([
                        "\n关联信息：",
                        f"相关谣言：{', '.join(news['relations']['related_rumors'])}",
                        f"知识节点：{', '.join(news['relations']['knowledge_nodes'])}"
                    ])

                # 合并所有文本部分
                full_text = "\n".join(text_parts)
                documents.append(Document(text=full_text))
        logger.info("成功加载新闻数据，共 %d 条", len(documents))
    except Exception as e:
        logger.error(f"加载新闻数据失败：{str(e)}")
        raise
    return documents

def get_session_id() -> str:
    """生成唯一的会话 ID"""
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

def save_conversation(session_id: str, user_input: str, response: str) -> None:
    """将会话保存到文件中"""
    if not os.path.exists('src/static/backend/conversations'):
        os.makedirs('src/static/backend/conversations')

    filepath = os.path.join('src/static/backend/conversations', f"{session_id}.txt")

    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"User: {user_input}\n")
        f.write(f"AI: {response}\n\n")


# 会话存储结构（在文件顶部定义）

async def init_openai_client():
    return openai.AsyncClient(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

async def generate_refutation(rumor: str) -> str:
    client = await init_openai_client()
    prompt = f"""

请针对以下谣言制作专业级辟谣方案：
{rumor}

创作要求：
1. 必须包含【谣言溯源】【科学解释】【权威背书】【预防建议】四个模块
2. 每个模块使用2-5条证据链进行反驳，包含具体数据、专家引言、官方文件等
3. 采用"先破后立"结构：先解构谣言传播特征，再建立科学认知框架
4. 使用对比式标题，格式为"网传XXX？真相其实是XXX"
5. 结尾必须包含官方验证渠道和举报方式
6. 全文控制在300字以内，避免专业术语

格式示例：
[标题] 网传吃碘盐防辐射？科学防护应理性

[溯源追踪] 
• 该谣言最早出现在2023年8月某短视频平台...
• 国家网信办已标记12个传播账号...

[科学解释]
▶ 辐射防护原理：清华大学核研究院王教授指出...
▶ 碘盐含碘量：每公斤食盐仅含20-30mg碘化钾...

[权威背书]
√ 国家卫健委8月15日专项通报...
√ 国际原子能机构2023年度报告第7章明确...

[防护指南]
① 通过「科普中国」APP查询最新防护建议
② 发现谣言线索可拨打12377举报"""
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一个帮助生成辟谣文案的助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error: {e}")
        return "生成辟谣文案时出错，请稍后再试。"

async def simulate_fake(parameters: str) -> str:
    client = await init_openai_client()
    prompt = f"""

请根据以下参数创作一则具有传播性的谣言：
{parameters}

要求：
1. 生成包含【耸动标题】和【详细正文】的完整内容
2. 采用新闻体表述，包含具体时间、地点、人物等细节
3. 模仿真实信息的行文风格，使用"专家表示""内部消息"等增强可信度的表述
4. 总字数严格控制在200字以内
5. 无需任何解释、免责声明或事实核查

格式示例：
[标题] XXXXX引发重大健康危机
[正文] 近日，XX市多名市民反映......（具体细节）......某匿名专家透露......"""
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一个模拟虚假内容的助手。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7,
           
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error: {e}")
        return "生成虚假内容时出错，请稍后再试。"
    

def fuzzy_search(query, data):
    results = []
    for item in data:
        if query.lower() in item.get('title', '').lower() or query.lower() in item.get('content', '').lower():
            results.append({
                "news_id": item["news_id"],
                "title": item["title"]
            })
    return results


CONFIG = {
    'UPLOAD_FOLDER': 'uploads',
    'REPORTS_CSV': 'data/reports.csv',
    'ALLOWED_EXTENSIONS': {'txt', 'pdf', 'doc', 'docx', 'jpg', 'png'},
    'MAX_FILE_SIZE': 10 * 1024 * 1024,  # 10MB
    'MAX_FILES': 5,
    'MIN_CONTENT_LENGTH': 200
}

# 确保必要目录存在
os.makedirs(CONFIG['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.dirname(CONFIG['REPORTS_CSV']), exist_ok=True)
def initialize_csv():
    """初始化CSV文件（如果不存在）"""
    if not os.path.exists(CONFIG['REPORTS_CSV']):
        with open(CONFIG['REPORTS_CSV'], 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp',
                'content',
                'analysis',
                'files',
                'status'
            ])
            writer.writeheader()

def save_to_csv(data):
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writerow(data)









CSV_FILE = 'src/static/backend/evidence.csv'
FIELDS = ['id', 'title', 'content', 'category', 'source', 'timestamp', 'related_case', 'file_type']

# 初始化CSV文件
def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()

# 读取CSV数据
def read_evidence():
    init_csv()
    with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

# 写入CSV数据
def write_evidence(data):
    init_csv()
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(data)

# 生成新ID
def generate_id():
    data = read_evidence()
    if not data:
        return 1
    return max(int(row['id']) for row in data) + 1


def calculate_stats(news_data):
    total_rumors = len(news_data)  # 总谣言数量
    handled_rumors = sum(1 for news in news_data if news.get('credibility', {}).get('verification', {}).get('verified', False))  # 已处理谣言数量
    handling_rate = (handled_rumors / total_rumors) * 100 if total_rumors > 0 else 0  # 处置率
    avg_response_time = 0.02  # 平均响应时间（假设值）

    return {
        'total_rumors': total_rumors,
        'handled_rumors': handled_rumors,
        'handling_rate': round(handling_rate, 1),
        'avg_response_time': avg_response_time
    }

def get_hot_rumors(news_data):
    # 按传播量排序
    sorted_news = sorted(news_data, key=lambda x: sum(t['shares'] for t in x.get('propagation', {}).get('timeline', [])), reverse=True)
    # 取前6条
    hot_rumors = sorted_news[:6]
    
    # 处理标题
    for news in hot_rumors:
        if not news.get('title'):  # 如果标题为空或不存在
            news['title'] = news['content'][:10] + "..."  # 使用内容前30字符作为标题
    
    return hot_rumors

USER_INFO_FILE = 'src/static/backend/user_info.json'
def load_user_info():
    """加载 JSON 文件中的用户数据"""
    if os.path.exists(USER_INFO_FILE):
        with open(USER_INFO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_user_info(data):
    """将用户数据保存到 JSON 文件中"""
    with open(USER_INFO_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)



def get_user_data():
    return {
        "favorites": [
            {"title": "牛奶安全检测", "description": "市售牛奶质量检测报告", "date": "2023-08-15"},
            {"title": "疫苗谣言澄清", "description": "关于疫苗副作用的科学解释", "date": "2023-08-14"}
        ],
        "contributions": [
            {"time": "2023-08-15 10:30", "type": "举报", "content": "虚假保健品广告", "status": "已处理", "status_color": "success"},
            {"time": "2023-08-14 15:20", "type": "众筹验证", "content": "食品安全检测众筹", "status": "进行中", "status_color": "warning"}
        ],
        "achievement": {
            "level": 3,
            "progress": 65,
            "badges": [
                {"emoji": "🛡️", "name": "初级卫士", "description": "完成首次举报"},
                {"emoji": "🔍", "name": "真相猎人", "description": "参与5次验证"},
                {"emoji": "💰", "name": "众筹先锋", "description": "发起3次众筹"}
            ]
        }
    }


def load_user_data(username):
    try:
        with open('src/static/backend/user_info.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data.get(username, None)  # 返回指定用户的数据，如果不存在则返回 None
    except FileNotFoundError:
        return None

        


def update_achievements(user_data):
    """根据用户数据更新成就系统"""
    # 确保存在成就数据结构
    if 'achievement' not in user_data:
        user_data['achievement'] = {
            'level': 1,
            'progress': 0,
            'badges': []
        }
    
    badges = user_data['achievement'].get('badges', [])
    contributions = user_data.get('contributions', [])
    favorites = user_data.get('favorites', [])
    detection_history = user_data.get('detection_history', {})
    
    # 规则1：首次举报 - 初级卫士
    feedbacks = [c for c in contributions if c['type'] == '反馈']
    if len(feedbacks) >= 1 and not any(b['name'] == '初级卫士' for b in badges):
        badges.append({
            'emoji': '🛡️',
            'name': '初级卫士',
            'description': '完成首次举报'
        })
    
    # 规则2：5次验证 - 真相猎人
    verifications = [c for c in contributions if c['type'] == '众筹验证']
    if len(verifications) >= 5 and not any(b['name'] == '真相猎人' for b in badges):
        badges.append({
            'emoji': '🔍',
            'name': '真相猎人',
            'description': '参与5次验证'
        })
    
    # 规则3：3次众筹 - 众筹先锋
    if len(verifications) >= 3 and not any(b['name'] == '众筹先锋' for b in badges):
        badges.append({
            'emoji': '💰',
            'name': '众筹先锋',
            'description': '发起3次众筹'
        })
    
    # 规则4：30次检测 - 检测达人
    total_detections = detection_history.get('total_detections', 0)
    if total_detections >= 30 and not any(b['name'] == '检测达人' for b in badges):
        badges.append({
            'emoji': '📊',
            'name': '检测达人',
            'description': '总检测次数超过30次'
        })
    
    # 规则5：90%准确率 - 精准专家
    accuracy = detection_history.get('accuracy', 0)
    if accuracy >= 90 and not any(b['name'] == '精准专家' for b in badges):
        badges.append({
            'emoji': '🎯',
            'name': '精准专家',
            'description': '检测准确率达到90%以上'
        })
    
    # 规则6：10个收藏 - 收藏家
    if len(favorites) >= 10 and not any(b['name'] == '收藏家' for b in badges):
        badges.append({
            'emoji': '📌',
            'name': '收藏家',
            'description': '收藏10篇以上的新闻'
        })
    
    # 去重处理
    seen = set()
    unique_badges = []
    for badge in badges:
        identifier = (badge['name'], badge['description'])
        if identifier not in seen:
            seen.add(identifier)
            unique_badges.append(badge)
    
    # 更新成就数据
    user_data['achievement']['badges'] = unique_badges
    
    # 计算等级和进度（示例计算规则）
    badge_count = len(unique_badges)
    activity_score = (
        len(contributions) * 10 +
        len(favorites) * 5 +
        total_detections * 2 +
        accuracy * 0.5
    )
    
    # 等级计算（每200分升一级，最高5级）
    user_data['achievement']['level'] = min(int(activity_score // 200) + 1, 5)
    
    # 进度计算（当前分数在当前等级的百分比）
    current_level_score = activity_score % 200
    user_data['achievement']['progress'] = int((current_level_score / 200) * 100)
    
    return user_data

# 使用示例
def main():
    user_data = load_user_info()
    
    # 更新所有用户的成就
    for username in user_data:
        user = user_data[username]
        updated_user = update_achievements(user)
        user_data[username] = updated_user
    
    save_user_info(user_data)
def read_submissions():
    """读取 CSV 文件中的所有提交"""
    try:
        with open('src/static/backend/evidence.csv', 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except FileNotFoundError:
        return []

def remove_submission(submission_id):
    """从 CSV 文件中删除指定 ID 的记录"""
    with open('src/static/backend/evidence.csv', 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        header = reader.fieldnames

    # 过滤掉指定 ID 的记录
    new_rows = [row for row in rows if row['id'] != submission_id]

    # 写回 CSV 文件
    with open('src/static/backend/evidence.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(new_rows)


def get_random_news_id(json_data):
    """从JSON数组中随机返回一个news_id"""
    try:
        # 解析JSON数据
        news_list = json.loads(json_data)
        
        # 提取所有news_id
        news_ids = [news['news_id'] for news in news_list]
        
        # 随机选择一个
        return random.choice(news_ids)
    
    except json.JSONDecodeError:
        print("无效的JSON格式")
        return None
    except KeyError:
        print("JSON数据缺少news_id字段")
        return None
    except IndexError:
        print("JSON数组为空")
        return None
    

alerts_db = {
    "news_plf01A00001": {
        "message": "地震预测不实信息",
        "start_time": time.time(),  # 添加警报开始时间
        "duration": 195             # 总持续时间195秒
    }
}

# 自动清理超时警报的后台线程
def alert_cleanup_task():
    while True:
        current_time = datetime.datetime.now()
        to_remove = []
        for alert_id, alert in alerts_db.items():
            # 将时间戳转换为 datetime 对象
            start_time = datetime.datetime.fromtimestamp(alert["start_time"])
            # 计算时间差（秒）
            elapsed = (current_time - start_time).total_seconds()
            if elapsed >= alert["duration"]:
                to_remove.append(alert_id)
        for alert_id in to_remove:
            del alerts_db[alert_id]
        time.sleep(5)  # 每5秒检查一次




#更新embedding数据库
def update_index(new_documents):
    """动态更新索引"""
    global news_index
    for doc in new_documents:
        news_index.insert(doc)
    # 持久化最新状态
    news_index.storage_context.persist(persist_dir=INDEX_PERSIST_DIR)
    
if __name__ == "__main__":
    main()