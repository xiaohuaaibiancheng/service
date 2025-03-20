"""
user_usage_tracker.py：用户功能使用统计

这个模块用于记录前台用户使用了哪些功能及使用次数，并以JSON格式存储。
提供了加载、保存和记录功能使用情况的函数。
"""

import os
import json
import logging
import threading
from datetime import datetime

# 用户使用统计的相关配置
USAGE_STATS_DIR = os.path.join(os.path.dirname(__file__), '../static/frontend', 'usage_stats')
USER_USAGE_FILE = os.path.join(USAGE_STATS_DIR, 'user_usage.json')

# 确保目录存在
if not os.path.exists(USAGE_STATS_DIR):
    os.makedirs(USAGE_STATS_DIR)

# 用于线程安全的锁
stats_lock = threading.Lock()

# 初始化用户功能使用统计数据
user_usage_stats = {
    # 新闻检测相关功能
    "news_detect_view": {"total": 0, "users": {}},        # 访问新闻检测页面
    "news_detect_submit": {"total": 0, "users": {}},      # 提交新闻检测请求
    "detect_url": {"total": 0, "users": {}},              # 使用URL检测功能
    "detect_multimodal": {"total": 0, "users": {}},       # 使用多模态检测功能
    "detect_file": {"total": 0, "users": {}},             # 使用文件检测功能
    "fake_news_classify": {"total": 0, "users": {}},      # 使用虚假新闻分类功能
    "news_segment_view": {"total": 0, "users": {}},       # 访问新闻分段检测页面
    "news_segment_analyze": {"total": 0, "users": {}},    # 执行新闻分段分析
    
    # AI检测相关功能
    "ai_detect_view": {"total": 0, "users": {}},          # 访问AI检测页面
    "detect_ai_text": {"total": 0, "users": {}},          # 使用AI文本检测功能
    "detect_ai_image": {"total": 0, "users": {}},         # 使用AI图片检测功能
    
    # 事实核查代理
    "agent_view": {"total": 0, "users": {}},              # 访问事实核查代理页面
    "agent_check": {"total": 0, "users": {}},             # 执行事实核查分析
    
    # 聚合分析
    "news_aggregate_view": {"total": 0, "users": {}},     # 访问新闻聚合页面
    "news_aggregate_search": {"total": 0, "users": {}},   # 执行新闻聚合搜索
    "detect_aggregate": {"total": 0, "users": {}},        # 使用聚合分析功能
    
    # 聊天相关
    "ai_chat_view": {"total": 0, "users": {}},            # 访问AI聊天页面
    "create_chat": {"total": 0, "users": {}},             # 创建新聊天
    "send_message": {"total": 0, "users": {}},            # 发送消息
    "share_chat": {"total": 0, "users": {}},              # 分享聊天
    "view_shared_chat": {"total": 0, "users": {}},        # 查看分享的聊天
    "reply_to_shared": {"total": 0, "users": {}},         # 回复分享的聊天
    
    # 数据管理
    "view_usage_stats": {"total": 0, "users": {}},        # 查看使用统计
    "download_stats": {"total": 0, "users": {}},          # 下载统计数据
    "reset_stats": {"total": 0, "users": {}},             # 重置统计数据
    
    # 基础页面访问
    "index_view": {"total": 0, "users": {}},              # 访问首页
    "about_view": {"total": 0, "users": {}},              # 访问关于页面
    "contact_view": {"total": 0, "users": {}},            # 访问联系页面
    
    # 高级功能
    "news_analyze": {"total": 0, "users": {}},            # 新闻深度分析
    "news_timeline": {"total": 0, "users": {}},           # 获取新闻传播时间线
    "view_segment": {"total": 0, "users": {}},            # 查看分段分析结果
    "update_settings": {"total": 0, "users": {}},         # 更新设置
}

# 加载现有统计数据（如果存在）
def load_user_usage_stats():
    """加载用户使用统计数据"""
    global user_usage_stats
    if os.path.exists(USER_USAGE_FILE):
        try:
            with open(USER_USAGE_FILE, 'r', encoding='utf-8') as f:
                loaded_stats = json.load(f)
                # 确保所有键都存在
                for key in user_usage_stats:
                    if key not in loaded_stats:
                        loaded_stats[key] = {"total": 0, "users": {}}
                    # 确保每个条目都有正确的结构
                    if not isinstance(loaded_stats[key], dict):
                        loaded_stats[key] = {"total": loaded_stats[key], "users": {}}
                    elif "total" not in loaded_stats[key]:
                        loaded_stats[key]["total"] = 0
                    elif "users" not in loaded_stats[key]:
                        loaded_stats[key]["users"] = {}
                user_usage_stats = loaded_stats
            logging.info(f"已加载用户使用统计数据：{USER_USAGE_FILE}")
        except Exception as e:
            logging.error(f"加载用户使用统计数据失败: {str(e)}")
    else:
        # 如果文件不存在，保存初始数据
        save_user_usage_stats()
        logging.info(f"已创建用户使用统计数据文件：{USER_USAGE_FILE}")

# 保存统计数据到文件
def save_user_usage_stats():
    """保存用户使用统计数据到JSON文件"""
    try:
        with open(USER_USAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_usage_stats, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logging.error(f"保存用户使用统计数据失败: {str(e)}")
        return False

# 记录功能使用
def record_user_usage(feature_name, username=None):
    """
    记录用户使用的功能
    
    Args:
        feature_name: 功能名称，必须是user_usage_stats中已定义的键
        username: 用户名，如果不提供则不记录
    
    Returns:
        bool: 操作是否成功
    """
    # 如果没有提供用户名，则不记录
    if not username:
        return False
        
    global user_usage_stats
    with stats_lock:
        if feature_name in user_usage_stats:
            # 增加总数
            user_usage_stats[feature_name]["total"] += 1
            
            # 增加特定用户的使用次数
            if username in user_usage_stats[feature_name]["users"]:
                user_usage_stats[feature_name]["users"][username] += 1
            else:
                user_usage_stats[feature_name]["users"][username] = 1
                
            # 保存到文件
            return save_user_usage_stats()
        else:
            logging.warning(f"尝试记录未定义的功能使用: {feature_name}")
            return False

# 获取使用统计数据
def get_user_usage_stats():
    """
    获取用户使用统计数据
    
    Returns:
        dict: 包含统计数据的字典
    """
    global user_usage_stats
    with stats_lock:
        # 创建一个副本返回，而不是直接返回原始字典
        stats_copy = {}
        for key, value in user_usage_stats.items():
            stats_copy[key] = {
                "total": value["total"],
                "users": value["users"].copy()
            }
            
        # 添加元数据
        stats_with_meta = {
            "stats": stats_copy,
            "total_usage": sum(item["total"] for item in stats_copy.values()),
            "unique_users": len(set(username for item in stats_copy.values() 
                                for username in item["users"].keys())),
            "last_updated": datetime.now().isoformat()
        }
        return stats_with_meta

# 获取最常用的功能
def get_most_used_features(limit=5):
    """
    获取最常用的功能
    
    Args:
        limit: 返回的功能数量
        
    Returns:
        list: 包含(feature_name, count)元组的列表，按使用次数降序排序
    """
    global user_usage_stats
    with stats_lock:
        # 按总使用次数排序
        sorted_features = sorted(
            [(key, value["total"]) for key, value in user_usage_stats.items()], 
            key=lambda x: x[1], 
            reverse=True
        )
        # 返回前N个
        return sorted_features[:limit]

# 获取最活跃的用户
def get_most_active_users(limit=5):
    """
    获取最活跃的用户
    
    Args:
        limit: 返回的用户数量
        
    Returns:
        list: 包含(username, count)元组的列表，按使用次数降序排序
    """
    global user_usage_stats
    with stats_lock:
        # 统计每个用户的总使用次数
        user_counts = {}
        for feature in user_usage_stats.values():
            for username, count in feature["users"].items():
                if username in user_counts:
                    user_counts[username] += count
                else:
                    user_counts[username] = count
                    
        # 按使用次数排序
        sorted_users = sorted(
            user_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 返回前N个
        return sorted_users[:limit]

# 重置特定功能的计数
def reset_feature_count(feature_name):
    """
    重置特定功能的使用计数
    
    Args:
        feature_name: 要重置的功能名称
        
    Returns:
        bool: 操作是否成功
    """
    global user_usage_stats
    with stats_lock:
        if feature_name in user_usage_stats:
            user_usage_stats[feature_name]["total"] = 0
            user_usage_stats[feature_name]["users"] = {}
            return save_user_usage_stats()
        else:
            logging.warning(f"尝试重置未定义的功能: {feature_name}")
            return False

# 重置所有功能计数
def reset_all_counts():
    """
    重置所有功能的使用计数
    
    Returns:
        bool: 操作是否成功
    """
    global user_usage_stats
    with stats_lock:
        for key in user_usage_stats:
            user_usage_stats[key]["total"] = 0
            user_usage_stats[key]["users"] = {}
        return save_user_usage_stats()

# 导出统计数据为JSON字符串
def export_stats_json():
    """
    导出统计数据为JSON字符串
    
    Returns:
        str: JSON格式的统计数据
    """
    stats_data = get_user_usage_stats()
    return json.dumps(stats_data, ensure_ascii=False, indent=4)

# 添加一个新的功能统计项
def add_feature(feature_name):
    """
    添加一个新的功能统计项
    
    Args:
        feature_name: 新功能名称
        
    Returns:
        bool: 操作是否成功
    """
    global user_usage_stats
    with stats_lock:
        if feature_name not in user_usage_stats:
            user_usage_stats[feature_name] = {"total": 0, "users": {}}
            return save_user_usage_stats()
        else:
            logging.warning(f"功能已存在: {feature_name}")
            return False

# 获取特定用户的使用情况
def get_user_activity(username):
    """
    获取特定用户的功能使用情况
    
    Args:
        username: 用户名
        
    Returns:
        dict: 包含用户使用的功能及次数
    """
    global user_usage_stats
    with stats_lock:
        user_activity = {}
        for feature_name, feature_data in user_usage_stats.items():
            if username in feature_data["users"]:
                user_activity[feature_name] = feature_data["users"][username]
        return user_activity

# 加载初始统计数据
load_user_usage_stats() 