from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
from pkg.platform.types import *

import asyncio
import aiohttp
import sqlite3
import json
import re
import logging
import yaml
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from urllib.parse import urlparse
from enum import Enum

# 先设置基础日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置管理器 - 已迁移到插件配置系统，不再使用
# class ConfigManager:
#     def __init__(self, config_path: str = "config.yaml"):
#         self.config_path = config_path
#         self.config = self.load_config()
#     
#     def load_config(self) -> Dict[str, Any]:
#         """加载配置文件"""
#         try:
#             if os.path.exists(self.config_path):
#                 with open(self.config_path, 'r', encoding='utf-8') as f:
#                     return yaml.safe_load(f)
#             else:
#                 logger.warning(f"Config file {self.config_path} not found, using default config")
#                 return self.get_default_config()
#         except Exception as e:
#             logger.error(f"Failed to load config: {e}")
#             return self.get_default_config()
#     
#     def get_default_config(self) -> Dict[str, Any]:
#         """获取默认配置"""
#         return {
#             "github_bot_api": {
#                 "base_url": "http://github_bot_api:8000",
#                 "timeout": 30,
#                 "retry_attempts": 3,
#                 "retry_delay": 5
#             },
#             "user_session": {
#                 "max_sessions_per_user": 5,
#                 "session_timeout_hours": 24,
#                 "max_question_length": 1000,
#                 "cleanup_interval_hours": 24
#             },
#             "database": {
#                 "path": "repo_insight.db",
#                 "connection_timeout": 30,
#                 "max_connections": 10
#             },
#             "polling": {
#                 "analysis_status_interval": 10,
#                 "query_result_interval": 5,
#                 "cleanup_interval": 3600
#             },
#             "logging": {
#                 "level": "INFO",
#                 "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
#             },
#             "features": {
#                 "enable_group_chat": True,
#                 "enable_private_chat": True,
#                 "require_mention_in_group": True,
#                 "auto_cleanup": True
#             }
#         }
#     
#     def get(self, key: str, default=None):
#         """获取配置值"""
#         keys = key.split('.')
#         value = self.config
#         for k in keys:
#             if isinstance(value, dict) and k in value:
#                 value = value[k]
#             else:
#                 return default
#         return value

# 初始化配置
# config_manager = ConfigManager()  # 已迁移到插件配置系统，不再使用

# 枚举定义
class UserState(Enum):
    IDLE = "idle"
    WAITING_FOR_REPO = "waiting_for_repo"
    ANALYZING = "analyzing"
    READY_FOR_QUERY = "ready_for_query"
    WAITING_FOR_ANSWER = "waiting_for_answer"

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# 数据模型
class UserSession:
    def __init__(self, user_id: str, state: UserState = UserState.IDLE, 
                 repo_url: str = None, analysis_task_id: str = None,
                 question: str = None, query_task_id: str = None, session_id: str = None):
        self.user_id = user_id
        self.state = state
        self.repo_url = repo_url
        self.analysis_task_id = analysis_task_id
        self.question = question
        self.query_task_id = query_task_id
        self.session_id = session_id  # 新增session_id字段
        self.last_activity = datetime.now()
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'state': self.state.value,
            'repo_url': self.repo_url,
            'analysis_task_id': self.analysis_task_id,
            'question': self.question,
            'query_task_id': self.query_task_id,
            'session_id': self.session_id,
            'last_activity': self.last_activity.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        session = cls(
            user_id=data['user_id'],
            state=UserState(data['state']),
            repo_url=data.get('repo_url'),
            analysis_task_id=data.get('analysis_task_id'),
            question=data.get('question'),
            query_task_id=data.get('query_task_id'),
            session_id=data.get('session_id')
        )
        if data.get('last_activity'):
            session.last_activity = datetime.fromisoformat(data['last_activity'])
        return session

# 状态管理器
class StateManager:
    def __init__(self, db_path: str = "repo_insight.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                repo_url TEXT,
                analysis_task_id TEXT,
                question TEXT,
                query_task_id TEXT,
                session_id TEXT,
                last_activity TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    
    def get_session(self, user_id: str) -> UserSession:
        """获取用户会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_sessions WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            data = {
                'user_id': row[0],
                'state': row[1],
                'repo_url': row[2],
                'analysis_task_id': row[3],
                'question': row[4],
                'query_task_id': row[5],
                'session_id': row[6],
                'last_activity': row[7]
            }
            return UserSession.from_dict(data)
        else:
            return UserSession(user_id)
    
    def save_session(self, session: UserSession):
        """保存用户会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_sessions 
            (user_id, state, repo_url, analysis_task_id, question, query_task_id, session_id, last_activity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.user_id,
            session.state.value,
            session.repo_url,
            session.analysis_task_id,
            session.question,
            session.query_task_id,
            session.session_id,
            session.last_activity.isoformat()
        ))
        conn.commit()
        conn.close()
    
    def cleanup_inactive_sessions(self, hours: int = 24):
        """清理不活跃的会话"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM user_sessions WHERE last_activity < ?",
            (cutoff_time.isoformat(),)
        )
        conn.commit()
        conn.close()

# GithubBot API 客户端
class GithubBotClient:
    def __init__(self, base_url: str = "http://github_bot_api:8000"):
        self.base_url = base_url
        self.session = None
    
    async def _get_session(self):
        """获取HTTP会话"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/health") as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def start_analysis(self, repo_url: str, embedding_config: Optional[Dict] = None) -> Optional[Dict]:
        """开始仓库分析"""
        try:
            session = await self._get_session()
            data = {"repo_url": repo_url}
            if embedding_config:
                data["embedding_config"] = embedding_config
            async with session.post(f"{self.base_url}/api/v1/repos/analyze", json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "session_id": result.get("session_id"),
                        "task_id": result.get("task_id")
                    }
                else:
                    logger.error(f"Analysis start failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Start analysis error: {e}")
            return None
    
    async def get_analysis_status(self, session_id: str) -> Optional[Dict]:
        """获取分析状态"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/v1/repos/status/{session_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Get analysis status failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Get analysis status error: {e}")
            return None
    
    async def submit_query(self, analysis_session_id: str, question: str, llm_config: Optional[Dict] = None) -> Optional[Dict]:
        """提交查询请求"""
        try:
            session = await self._get_session()
            data = {
                "session_id": analysis_session_id,
                "question": question,
                "generation_mode": "plugin"
            }
            if llm_config:
                data["llm_config"] = llm_config
            
            async with session.post(f"{self.base_url}/api/v1/repos/query", json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "session_id": result.get("session_id"),
                        "task_id": result.get("task_id")
                    }
                else:
                    logger.error(f"Submit query failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Submit query error: {e}")
            return None
    
    async def get_query_status(self, session_id: str) -> Optional[Dict]:
        """获取查询状态"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/v1/repos/query/status/{session_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Get query status failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Get query status error: {e}")
            return None
    
    async def get_query_result(self, session_id: str) -> Optional[Dict]:
        """获取查询结果"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/v1/repos/query/result/{session_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Get query result failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Get query result error: {e}")
            return None
    
    async def cancel_analysis(self, session_id: str) -> Optional[Dict]:
        """取消仓库分析任务"""
        try:
            session = await self._get_session()
            async with session.post(f"{self.base_url}/api/v1/repos/analyze/{session_id}/cancel") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Cancel analysis failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Cancel analysis error: {e}")
            return None
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None

# 消息处理器
class MessageHandler:
    def __init__(self, state_manager: StateManager, github_client: GithubBotClient, plugin_instance):
        self.state_manager = state_manager
        self.github_client = github_client
        self.plugin_instance = plugin_instance
    
    async def handle(self, ctx: EventContext, message: str, user_id: str) -> str:
        """处理用户消息"""
        session = self.state_manager.get_session(user_id)
        session.last_activity = datetime.now()
        
        # 处理指令
        if message.startswith('/'):
            response = await self.handle_command(session, message)
        else:
            # 根据状态处理消息
            if session.state == UserState.WAITING_FOR_REPO:
                response = await self.handle_repo_url(session, message)
            elif session.state == UserState.READY_FOR_QUERY:
                response = await self.handle_question(session, message, ctx)
            elif session.state == UserState.WAITING_FOR_ANSWER:
                response = "正在处理您的问题，请稍候..."
            else:
                response = "请使用 /repo 命令开始分析GitHub仓库，或使用 /help 查看帮助信息。"
        
        self.state_manager.save_session(session)
        return response
    
    async def handle_command(self, session: UserSession, command: str) -> str:
        """处理指令"""
        if command == "/repo":
            session.state = UserState.WAITING_FOR_REPO
            return "请发送要分析的GitHub仓库URL（例如：https://github.com/user/repo）"
        
        elif command == "/exit":
            session.state = UserState.IDLE
            session.repo_url = None
            session.analysis_task_id = None
            session.question = None
            session.query_task_id = None
            session.session_id = None
            return "已退出当前会话，使用 /repo 开始新的分析。"
        
        elif command == "/status":
            if session.state == UserState.IDLE:
                return "当前状态：空闲\n使用 /repo 开始分析GitHub仓库"
            elif session.state == UserState.WAITING_FOR_REPO:
                return "当前状态：等待仓库URL\n请发送GitHub仓库URL"
            elif session.state == UserState.ANALYZING:
                return f"当前状态：正在分析仓库\n仓库：{session.repo_url}\n请稍候..."
            elif session.state == UserState.READY_FOR_QUERY:
                return f"当前状态：准备就绪\n仓库：{session.repo_url}\n可以开始提问了！"
            elif session.state == UserState.WAITING_FOR_ANSWER:
                return f"当前状态：等待回答\n问题：{session.question}\n正在处理中..."
        
        elif command == "/cancel":
            if session.state == UserState.ANALYZING and session.session_id:
                # 取消分析任务
                result = await self.github_client.cancel_analysis(session.session_id)
                if result:
                    # 重置会话状态
                    session.state = UserState.IDLE
                    session.repo_url = None
                    session.analysis_task_id = None
                    session.session_id = None
                    return "✅ 已成功取消分析任务。使用 /repo 开始新的分析。"
                else:
                    return "❌ 取消分析任务失败，请稍后再试。"
            else:
                return "当前没有正在进行的分析任务可以取消。"
        
        elif command == "/help":
            return (
                "RepoInsight - GitHub仓库智能分析助手\n\n"
                "可用指令：\n"
                "/repo - 开始分析新的GitHub仓库\n"
                "/status - 查看当前状态\n"
                "/cancel - 取消当前分析任务\n"
                "/exit - 退出当前会话\n"
                "/help - 显示帮助信息\n\n"
                "使用流程：\n"
                "1. 发送 /repo 命令\n"
                "2. 提供GitHub仓库URL\n"
                "3. 等待分析完成\n"
                "4. 开始提问关于代码的问题"
            )
        
        else:
            return "未知指令，使用 /help 查看可用指令。"
    
    def validate_github_url(self, url: str) -> bool:
        """验证GitHub URL"""
        pattern = r'^https://github\.com/[\w.-]+/[\w.-]+/?$'
        return bool(re.match(pattern, url.strip()))
    
    async def handle_repo_url(self, session: UserSession, url: str) -> str:
        """处理仓库URL"""
        url = url.strip()
        
        if not self.validate_github_url(url):
            return "请提供有效的GitHub仓库URL，格式：https://github.com/user/repo"
        
        # 检查GithubBot服务是否可用
        if not await self.github_client.health_check():
            return "GithubBot服务暂时不可用，请稍后再试。"
        
        # 获取默认embedding配置
        embedding_config = self.plugin_instance.get_embedding_config()
        
        # 开始分析
        result = await self.github_client.start_analysis(url, embedding_config)
        if result and result.get("session_id"):
            session.state = UserState.ANALYZING
            session.repo_url = url
            session.analysis_task_id = result.get("task_id")
            session.session_id = result.get("session_id")  # 保存分析会话ID
            return f"✅ 已收到仓库链接，正在请求分析，请稍候... 这可能需要几分钟时间。\n仓库：{url}\n会话ID：{session.session_id}"
        else:
            return "启动分析失败，请检查仓库URL是否正确或稍后再试。"
    
    async def handle_question(self, session: UserSession, question: str, ctx: EventContext) -> str:
        """处理问题（异步）"""
        if not session.session_id:
            return "请先使用 /repo 命令分析一个仓库。"
        
        # 检查问题长度
        max_length = 2000  # 固定长度限制
        if len(question) > max_length:
            return f"问题太长了，请控制在{max_length}个字符以内。"
        
        # 获取默认LLM配置
        llm_config = self.plugin_instance.get_llm_config()
        
        # 提交查询请求
        result = await self.github_client.submit_query(session.session_id, question, llm_config)
        if result and result.get("session_id"):
            session.state = UserState.WAITING_FOR_ANSWER
            session.question = question
            session.query_task_id = result.get("task_id")
            # 注意：这里的session_id是查询会话ID，不同于分析会话ID
            query_session_id = result.get("session_id")
            return f"✅ 已收到您的问题：\"{question}\"\n正在为您查找答案，请稍候... 答案准备好后会立即通知您。\n查询会话ID：{query_session_id}"
        else:
            return "提问失败，请稍后再试。"

# 任务调度器
class TaskScheduler:
    def __init__(self, state_manager: StateManager, github_client: GithubBotClient, plugin_instance):
        self.state_manager = state_manager
        self.github_client = github_client
        self.plugin_instance = plugin_instance
        self.running = False
        self.tasks = set()
    
    async def start(self):
        """启动调度器"""
        if not self.running:
            self.running = True
            # 启动后台任务
            task1 = asyncio.create_task(self.poll_analysis_status())
            task2 = asyncio.create_task(self.poll_query_results())
            task3 = asyncio.create_task(self.cleanup_inactive_users())
            
            self.tasks.update([task1, task2, task3])
            logger.info("TaskScheduler started")
    
    async def stop(self):
        """停止调度器"""
        self.running = False
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()
        logger.info("TaskScheduler stopped")
    
    async def poll_analysis_status(self):
        """轮询分析状态"""
        while self.running:
            try:
                # 获取所有正在分析的会话
                conn = sqlite3.connect(self.state_manager.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id FROM user_sessions WHERE state = ?",
                    (UserState.ANALYZING.value,)
                )
                user_ids = [row[0] for row in cursor.fetchall()]
                conn.close()
                
                for user_id in user_ids:
                    session = self.state_manager.get_session(user_id)
                    if session.session_id:  # 使用session_id而不是analysis_task_id
                        status = await self.github_client.get_analysis_status(session.session_id)
                        if status:
                            status_value = status.get('status')
                            
                            if status_value == 'success':
                                session.state = UserState.READY_FOR_QUERY
                                self.state_manager.save_session(session)
                                
                                # 发送通知
                                message = f"✅ 仓库分析完成！\n仓库：{session.repo_url}\n现在可以开始提问了。请直接发送您的问题。"
                                await self.send_message_to_user(user_id, message)
                            
                            elif status_value == 'failed':
                                session.state = UserState.IDLE
                                session.repo_url = None
                                session.analysis_task_id = None
                                session.question = None
                                session.query_task_id = None
                                session.session_id = None
                                self.state_manager.save_session(session)
                                
                                # 发送错误通知
                                error_msg = status.get('error', '未知错误')
                                message = f"❌ 仓库分析失败：{error_msg}\n请使用 /repo 重新开始。"
                                await self.send_message_to_user(user_id, message)
                            
                            elif status_value == 'cancelled':
                                session.state = UserState.IDLE
                                session.repo_url = None
                                session.analysis_task_id = None
                                session.question = None
                                session.query_task_id = None
                                session.session_id = None
                                self.state_manager.save_session(session)
                                
                                # 发送取消通知
                                message = f"🛑 仓库分析已被取消\n请使用 /repo 重新开始分析。"
                                await self.send_message_to_user(user_id, message)
                
                analysis_interval = 10  # 固定轮询间隔
                await asyncio.sleep(analysis_interval)
            
            except Exception as e:
                logger.error(f"Poll analysis status error: {e}")
                await asyncio.sleep(30)  # 出错时等待更长时间
    
    async def poll_query_results(self):
        """轮询查询结果"""
        while self.running:
            try:
                # 获取所有等待回答的会话
                conn = sqlite3.connect(self.state_manager.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id FROM user_sessions WHERE state = ?",
                    (UserState.WAITING_FOR_ANSWER.value,)
                )
                user_ids = [row[0] for row in cursor.fetchall()]
                conn.close()
                
                for user_id in user_ids:
                    session = self.state_manager.get_session(user_id)
                    if session.query_task_id:  # 使用query_task_id查询状态
                        # 先查询状态
                        status_result = await self.github_client.get_query_status(session.query_task_id)
                        if status_result:
                            status = status_result.get('status')
                            
                            if status == 'success':
                                # 获取结果
                                result = await self.github_client.get_query_result(session.query_task_id)
                                if result:
                                    answer = result.get('answer', '无法获取答案')
                                    question = session.question  # 保存问题用于显示
                                    
                                    # 更新状态
                                    session.state = UserState.READY_FOR_QUERY
                                    session.question = None
                                    session.query_task_id = None
                                    # 保持session_id，用于后续查询
                                    self.state_manager.save_session(session)
                                    
                                    # 发送答案
                                    message = f"💡 **问题**：{question}\n\n📝 **答案**：\n{answer}"
                                    await self.send_message_to_user(user_id, message)
                            
                            elif status == 'failure':
                                error_msg = status_result.get('error', '处理失败')
                                question = session.question  # 保存问题用于显示
                                
                                # 更新状态
                                session.state = UserState.READY_FOR_QUERY
                                session.question = None
                                session.query_task_id = None
                                # 保持session_id，用于后续查询
                                self.state_manager.save_session(session)
                                
                                # 发送错误消息
                                message = f"❌ **问题**：{question}\n\n**错误**：{error_msg}"
                                await self.send_message_to_user(user_id, message)
                            
                            elif status == 'revoked':
                                question = session.question  # 保存问题用于显示
                                
                                # 更新状态
                                session.state = UserState.READY_FOR_QUERY
                                session.question = None
                                session.query_task_id = None
                                # 保持session_id，用于后续查询
                                self.state_manager.save_session(session)
                                
                                # 发送取消消息
                                message = f"🚫 **问题**：{question}\n\n查询任务已被取消。"
                                await self.send_message_to_user(user_id, message)
                
                query_interval = 5  # 固定轮询间隔
                await asyncio.sleep(query_interval)
            
            except Exception as e:
                logger.error(f"Poll query results error: {e}")
                await asyncio.sleep(15)  # 出错时等待更长时间
    
    async def cleanup_inactive_users(self):
        """清理不活跃用户"""
        while self.running:
            try:
                cleanup_hours = 24  # 固定清理间隔
                self.state_manager.cleanup_inactive_sessions(cleanup_hours)
                cleanup_interval = 3600  # 固定清理间隔
                await asyncio.sleep(cleanup_interval)
            except Exception as e:
                logger.error(f"Cleanup inactive users error: {e}")
                await asyncio.sleep(3600)
    
    async def send_message_to_user(self, user_id: str, message: str):
        """发送消息给用户"""
        try:
            adapters = self.plugin_instance.host.get_platform_adapters()
            if adapters and len(adapters) > 0:
                adapter = adapters[0]  # 使用第一个可用的适配器
                message_chain = MessageChain([
                    Plain(message)
                ])
                await self.plugin_instance.host.send_active_message(
                    adapter=adapter,
                    target_type="person",
                    target_id=user_id,
                    message=message_chain
                )
            else:
                logger.warning(f"No platform adapters available to send message to user {user_id}")
        except Exception as e:
            logger.error(f"Send message to user {user_id} failed: {e}")

# 主插件类
@register(name="RepoInsight", description="GitHub仓库智能分析插件", version="1.0.0", author="oGYCo")
class RepoInsightPlugin(BasePlugin):
    
    def __init__(self, host: APIHost):
        super().__init__(host)
        # 使用 LangBot 插件配置系统
        self.plugin_config = {}
        # LangBot 插件管理器会设置 self.config
        self.config = {}
        
        # 初始化组件
        db_path = self.get_config('database_path', 'repo_insight.db')
        github_base_url = self.get_githubbot_base_url()
        
        self.state_manager = StateManager(db_path)
        self.github_client = GithubBotClient(github_base_url)
        self.message_handler = MessageHandler(self.state_manager, self.github_client, self)
        self.task_scheduler = TaskScheduler(self.state_manager, self.github_client, self)
    
    def get_config(self, key: str, default=None):
        """从插件配置中获取值"""
        # 优先从 self.config 获取（LangBot 插件管理器设置的）
        if hasattr(self, 'config') and self.config:
            return self.config.get(key, default)
        # 备用从 self.plugin_config 获取
        return self.plugin_config.get(key, default)
    
    def get_embedding_config(self):
        """获取向量模型配置"""
        return {
            "provider": self.get_config("embedding_provider", "openai"),
            "model_name": self.get_config("embedding_model", "text-embedding-3-small"),
            "api_key": self.get_config("embedding_api_key", "")
        }
    
    def get_llm_config(self):
        """获取语言模型配置"""
        return {
            "provider": self.get_config("llm_provider", "openai"),
            "model_name": self.get_config("llm_model", "gpt-4o-mini"),
            "api_key": self.get_config("llm_api_key", ""),
            "max_tokens": self.get_config("llm_max_tokens", 4096),
            "temperature": self.get_config("llm_temperature", 0.7)
        }
    
    def get_generation_mode(self):
        """获取生成模式"""
        return self.get_config("generation_mode", "service")
    
    def get_githubbot_base_url(self):
        """获取 GithubBot 基础 URL"""
        return self.get_config("githubbot_base_url", "http://api:8000")
    
    def update_config(self, new_config: dict):
        """更新插件配置"""
        self.plugin_config.update(new_config)
        # 同时更新 self.config（与 LangBot 插件管理器保持一致）
        if hasattr(self, 'config'):
            self.config.update(new_config)
        # 更新 GitHub 客户端的基础 URL
        new_base_url = self.get_githubbot_base_url()
        if hasattr(self, 'github_client'):
            self.github_client.base_url = new_base_url
        logger.info(f"Plugin config updated: {list(new_config.keys())}")
    
    async def initialize(self):
        """异步初始化"""
        logger.info("RepoInsight plugin initializing...")
        await self.task_scheduler.start()
        logger.info("RepoInsight plugin initialized successfully")
    
    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        """处理私聊消息"""
        # 检查是否启用私聊功能
        if not self.get_config('enable_private_chat', True):
            return
        
        message = ctx.event.text_message
        user_id = str(ctx.event.sender_id)
        
        try:
            response = await self.message_handler.handle(ctx, message, user_id)
            ctx.add_return("reply", [response])
            ctx.prevent_default()
        except Exception as e:
            logger.error(f"Handle person message error: {e}")
            ctx.add_return("reply", ["处理消息时发生错误，请稍后再试。"])
            ctx.prevent_default()
    
    @handler(GroupNormalMessageReceived)
    async def group_normal_message_received(self, ctx: EventContext):
        """处理群聊消息"""
        # 检查是否启用群聊功能
        if not self.get_config('enable_group_chat', True):
            return
        
        message = ctx.event.text_message
        user_id = str(ctx.event.sender_id)
        
        # 检查是否需要@机器人
        require_mention = self.get_config('require_mention_in_group', True)
        should_process = False
        
        if message.startswith('/'):
            should_process = True
        elif require_mention and '@' in message:
            should_process = True
        elif not require_mention:
            should_process = True
        
        if should_process:
            try:
                response = await self.message_handler.handle(ctx, message, user_id)
                ctx.add_return("reply", [response])
                ctx.prevent_default()
            except Exception as e:
                logger.error(f"Handle group message error: {e}")
                ctx.add_return("reply", ["处理消息时发生错误，请稍后再试。"])
                ctx.prevent_default()
    
    def __del__(self):
        """插件卸载时的清理工作"""
        try:
            asyncio.create_task(self.cleanup())
        except Exception as e:
            logger.error(f"Plugin cleanup error: {e}")
    
    async def cleanup(self):
        """清理资源"""
        await self.task_scheduler.stop()
        await self.github_client.close()
        logger.info("RepoInsight plugin cleaned up")