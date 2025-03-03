from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import uuid

class CredibilityDimensionScores(BaseModel):
    """新闻可信度的各维度评分"""
    source: float = Field(default=0.0, description="来源可信度评分")
    content: float = Field(default=0.0, description="内容可信度评分")
    logic: float = Field(default=0.0, description="逻辑可信度评分")
    propagation: float = Field(default=0.0, description="传播可信度评分")
    AI: float = Field(default=0.0, description="AI生成内容评分")
    content1: str = Field(default="", description="内容分析1")
    content2: str = Field(default="", description="内容分析2")

class VerificationInfo(BaseModel):
    """验证信息"""
    crowdsource_progress: int = Field(default=0, description="众包验证进度")
    verified: bool = Field(default=False, description="是否已验证")

class Credibility(BaseModel):
    """新闻可信度信息"""
    score: float = Field(default=0.0, description="总体可信度评分")
    dimension_scores: CredibilityDimensionScores = Field(default_factory=CredibilityDimensionScores, description="各维度评分")
    verification: VerificationInfo = Field(default_factory=VerificationInfo, description="验证信息")

class TimelineEvent(BaseModel):
    """传播时间线事件"""
    timestamp: str = Field(description="事件时间戳")
    platform: str = Field(description="传播平台")
    shares: int = Field(default=0, description="分享数量")
    geo_distribution: Dict[str, int] = Field(default_factory=dict, description="地理分布")

class UserProfile(BaseModel):
    """用户画像"""
    age_dist: Dict[str, int] = Field(default_factory=dict, description="年龄分布")
    device_ratio: Dict[str, int] = Field(default_factory=dict, description="设备比例")

class Propagation(BaseModel):
    """传播信息"""
    timeline: List[TimelineEvent] = Field(default_factory=list, description="传播时间线")
    user_profile: UserProfile = Field(default_factory=UserProfile, description="用户画像")

class Relations(BaseModel):
    """关联信息"""
    related_rumors: List[str] = Field(default_factory=list, description="相关谣言")
    knowledge_nodes: List[str] = Field(default_factory=list, description="知识节点")

class NewsAnalysisResult(BaseModel):
    """新闻分析结果"""
    news_id: str = Field(default_factory=lambda: f"news_{uuid.uuid4().hex[:8]}", description="新闻ID")
    publish_time: str = Field(default_factory=lambda: datetime.now().strftime("%Y/%m/%d"), description="发布时间")
    platform: str = Field(default="", description="平台")
    check_time: str = Field(default_factory=lambda: datetime.now().strftime("%Y/%m/%d"), description="检查时间")
    label: str = Field(default="未知", description="标签")
    url: str = Field(default="", description="URL")
    title: str = Field(default="", description="标题")
    content: str = Field(default="", description="内容")
    pic_url: str = Field(default="", description="图片URL")
    hashtag: str = Field(default="", description="话题标签")
    summary: str = Field(default="", description="摘要")
    credibility: Credibility = Field(default_factory=Credibility, description="可信度信息")
    propagation: Propagation = Field(default_factory=Propagation, description="传播信息")
    relations: Relations = Field(default_factory=Relations, description="关联信息")
    iscredit: bool = Field(default=False, description="是否可信")
    location: str = Field(default="", description="地点") 
    conclusion: str = Field(default="", description="总结整个新闻是否可信，给出综合结论")