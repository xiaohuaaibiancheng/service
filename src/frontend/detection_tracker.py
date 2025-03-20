import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class DetectionTracker:
    def __init__(self):
        self.user_info_file = os.path.join(os.path.dirname(__file__), '../static/backend/user_info.json')
        self._ensure_user_info_file()
        print(f"初始化DetectionTracker，文件路径: {self.user_info_file}")
        print(f"文件是否存在: {os.path.exists(self.user_info_file)}")
    
    def _ensure_user_info_file(self):
        """确保user_info文件存在"""
        if not os.path.exists(os.path.dirname(self.user_info_file)):
            os.makedirs(os.path.dirname(self.user_info_file))
            print(f"创建目录: {os.path.dirname(self.user_info_file)}")
        if not os.path.exists(self.user_info_file):
            with open(self.user_info_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=4)
            print(f"创建user_info.json文件")
    
    def _load_user_info(self) -> Dict:
        """加载用户信息"""
        try:
            with open(self.user_info_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载用户信息失败: {str(e)}")
            return {}
    
    def _save_user_info(self, data: Dict):
        """保存用户信息"""
        try:
            print(f"正在保存用户信息到文件: {self.user_info_file}")
            print(f"保存的数据: {json.dumps(data, ensure_ascii=False)[:100]}...")
            with open(self.user_info_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print("保存用户信息成功")
        except Exception as e:
            print(f"保存用户信息失败: {str(e)}")
    
    def add_detection_record(self, username: str, detection_type: str, result: str, accuracy: float):
        """
        添加检测记录
        
        Args:
            username: 用户名
            detection_type: 检测类型 ('fake_news', 'consistency', 'ai_generated')
            result: 检测结果
            accuracy: 准确率
        """
        print(f"添加检测记录: username={username}, type={detection_type}, result={result}, accuracy={accuracy}")
        
        if not username:
            print("用户名为空，跳过添加检测记录")
            return
            
        try:
            user_info = self._load_user_info()
            print(f"加载用户信息成功，用户数量: {len(user_info)}")
            
            # 如果用户不存在，创建用户
            if username not in user_info:
                print(f"用户 {username} 不存在，创建新用户")
                user_info[username] = {}
            
            # 如果用户没有detection_history，创建它
            if 'detection_history' not in user_info[username]:
                print(f"用户 {username} 没有detection_history，创建它")
                user_info[username]['detection_history'] = {
                    "total_detections": 0,
                    "accuracy": 0.0,
                    "records": []
                }
            
            # 添加新记录
            new_record = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "result": result,
                "status": "成功" if accuracy >= 70 else "失败",
                "status_color": "success" if accuracy >= 70 else "danger",
                "accuracy": round(accuracy, 1)
            }
            print(f"创建新记录: {new_record}")
            
            # 更新统计数据
            detection_history = user_info[username]['detection_history']
            detection_history['records'].insert(0, new_record)  # 在列表开头插入新记录
            detection_history['total_detections'] += 1
            
            # 限制记录数量为最新的10条
            if len(detection_history['records']) > 10:
                detection_history['records'] = detection_history['records'][:10]
            
            # 计算平均准确率
            total_accuracy = sum(record["accuracy"] for record in detection_history["records"])
            detection_history["accuracy"] = round(total_accuracy / len(detection_history["records"]), 1)
            
            # 保存用户信息
            self._save_user_info(user_info)
            print(f"成功添加检测记录并保存用户信息")
        except Exception as e:
            print(f"添加检测记录异常: {str(e)}")
    
    def get_user_history(self, username: str) -> Optional[Dict]:
        """获取用户的检测历史"""
        user_info = self._load_user_info()
        if username in user_info and 'detection_history' in user_info[username]:
            return user_info[username]['detection_history']
        return None
    
    def clear_user_history(self, username: str):
        """清除用户的检测历史"""
        user_info = self._load_user_info()
        if username in user_info and 'detection_history' in user_info[username]:
            user_info[username]['detection_history'] = {
                "total_detections": 0,
                "accuracy": 0.0,
                "records": []
            }
            self._save_user_info(user_info)

# 创建全局实例
detection_tracker = DetectionTracker() 