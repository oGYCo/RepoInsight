from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
import pkg.platform.types as platform_types

import asyncio
import aiohttp
import sqlite3
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from urllib.parse import urlparse
from enum import Enum

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 枚举定义
class UserState(Enum):
    IDLE = "idle"
    WAITING_FOR_REPO = "waiting_for_repo"
    ANALYZING = "analyzing"
    READY_FOR_QUESTIONS = "ready_for_questions"
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
                 question: str = None, query_task_id: str = None):
        self.user_id = user_id
        self.state = state
        self.repo_url = repo_url
        self.analysis_task_id = analysis_task_id
        self.question = question
        self.query_task_id = query_task_id
        self.last_activity = datetime.now()
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'state': self.state.value,
            'repo_url': self.repo_url,
            'analysis_task_id': self.analysis_task_id,
            'question': self.question,
            'query_task_id': self.query_task_id,
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
            query_task_id=data.get('query_task_id')
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
                'last_activity': row[6]
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
            (user_id, state, repo_url, analysis_task_id, question, query_task_id, last_activity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session.user_id,
            session.state.value,
            session.repo_url,
            session.analysis_task_id,
            session.question,
            session.query_task_id,
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
    def __init__(self, base_url: str = "http://localhost:8000"):
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
    
    async def start_analysis(self, repo_url: str) -> Optional[str]:
        """开始仓库分析"""
        try:
            session = await self._get_session()
            data = {"repo_url": repo_url}
            async with session.post(f"{self.base_url}/analyze", json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("task_id")
                else:
                    logger.error(f"Analysis start failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Start analysis error: {e}")
            return None
    
    async def get_analysis_status(self, task_id: str) -> Optional[Dict]:
        """获取分析状态"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/analyze/{task_id}/status") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Get analysis status failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Get analysis status error: {e}")
            return None
    
    async def ask_question(self, repo_url: str, question: str) -> Optional[str]:
        """提问"""
        try:
            session = await self._get_session()
            data = {
                "repo_url": repo_url,
                "question": question
            }
            async with session.post(f"{self.base_url}/query", json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("task_id")
                else:
                    logger.error(f"Ask question failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Ask question error: {e}")
            return None
    
    async def get_query_result(self, task_id: str) -> Optional[Dict]:
        """获取查询结果"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/query/{task_id}/result") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Get query result failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Get query result error: {e}")
            return None
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None

# 消息处理器
class MessageHandler:
    def __init__(self, state_manager: StateManager, github_client: GithubBotClient):
        self.state_manager = state_manager
        self.github_client = github_client
    
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
            elif session.state == UserState.READY_FOR_QUESTIONS:
                response = await self.handle_question(session, message, ctx)
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
            return "已退出当前会话，使用 /repo 开始新的分析。"
        
        elif command == "/status":
            if session.state == UserState.IDLE:
                return "当前状态：空闲\n使用 /repo 开始分析GitHub仓库"
            elif session.state == UserState.WAITING_FOR_REPO:
                return "当前状态：等待仓库URL\n请发送GitHub仓库URL"
            elif session.state == UserState.ANALYZING:
                return f"当前状态：正在分析仓库\n仓库：{session.repo_url}\n请稍候..."
            elif session.state == UserState.READY_FOR_QUESTIONS:
                return f"当前状态：准备就绪\n仓库：{session.repo_url}\n可以开始提问了！"
            elif session.state == UserState.WAITING_FOR_ANSWER:
                return f"当前状态：等待回答\n问题：{session.question}\n正在处理中..."
        
        elif command == "/help":
            return (
                "RepoInsight - GitHub仓库智能分析助手\n\n"
                "可用指令：\n"
                "/repo - 开始分析新的GitHub仓库\n"
                "/status - 查看当前状态\n"
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
        
        # 开始分析
        task_id = await self.github_client.start_analysis(url)
        if task_id:
            session.state = UserState.ANALYZING
            session.repo_url = url
            session.analysis_task_id = task_id
            return f"开始分析仓库：{url}\n任务ID：{task_id}\n请稍候，分析完成后会自动通知您。"
        else:
            return "启动分析失败，请检查仓库URL是否正确或稍后再试。"
    
    async def handle_question(self, session: UserSession, question: str, ctx: EventContext) -> str:
        """处理问题（异步）"""
        if not session.repo_url:
            return "请先使用 /repo 命令分析一个仓库。"
        
        # 开始查询
        task_id = await self.github_client.ask_question(session.repo_url, question)
        if task_id:
            session.state = UserState.WAITING_FOR_ANSWER
            session.question = question
            session.query_task_id = task_id
            return f"正在处理您的问题：{question}\n任务ID：{task_id}\n请稍候，处理完成后会自动回复您。"
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
                    if session.analysis_task_id:
                        status = await self.github_client.get_analysis_status(session.analysis_task_id)
                        if status:
                            if status.get('status') == 'completed':
                                session.state = UserState.READY_FOR_QUESTIONS
                                self.state_manager.save_session(session)
                                
                                # 发送通知
                                message = f"仓库分析完成！\n仓库：{session.repo_url}\n现在可以开始提问了。"
                                await self.send_message_to_user(user_id, message)
                            
                            elif status.get('status') == 'failed':
                                session.state = UserState.IDLE
                                session.repo_url = None
                                session.analysis_task_id = None
                                self.state_manager.save_session(session)
                                
                                # 发送错误通知
                                error_msg = status.get('error', '未知错误')
                                message = f"仓库分析失败：{error_msg}\n请使用 /repo 重新开始。"
                                await self.send_message_to_user(user_id, message)
                
                await asyncio.sleep(10)  # 每10秒检查一次
            
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
                    if session.query_task_id:
                        result = await self.github_client.get_query_result(session.query_task_id)
                        if result:
                            status = result.get('status')
                            
                            if status == 'completed':
                                answer = result.get('answer', '无法获取答案')
                                session.state = UserState.READY_FOR_QUESTIONS
                                session.question = None
                                session.query_task_id = None
                                self.state_manager.save_session(session)
                                
                                # 发送答案
                                message = f"问题：{session.question}\n\n答案：{answer}"
                                await self.send_message_to_user(user_id, message)
                            
                            elif status == 'failed':
                                error_msg = result.get('error', '处理失败')
                                session.state = UserState.READY_FOR_QUESTIONS
                                session.question = None
                                session.query_task_id = None
                                self.state_manager.save_session(session)
                                
                                # 发送错误信息
                                message = f"问题处理失败：{error_msg}\n请重新提问。"
                                await self.send_message_to_user(user_id, message)
                
                await asyncio.sleep(5)  # 每5秒检查一次
            
            except Exception as e:
                logger.error(f"Poll query results error: {e}")
                await asyncio.sleep(15)  # 出错时等待更长时间
    
    async def cleanup_inactive_users(self):
        """清理不活跃用户"""
        while self.running:
            try:
                self.state_manager.cleanup_inactive_sessions(24)  # 清理24小时不活跃的会话
                await asyncio.sleep(3600)  # 每小时清理一次
            except Exception as e:
                logger.error(f"Cleanup inactive users error: {e}")
                await asyncio.sleep(3600)
    
    async def send_message_to_user(self, user_id: str, message: str):
        """发送消息给用户"""
        try:
            adapters = self.plugin_instance.host.get_platform_adapters()
            if adapters:
                adapter = adapters[0]  # 使用第一个可用的适配器
                message_chain = platform_types.MessageChain([
                    platform_types.Plain(message)
                ])
                await self.plugin_instance.host.send_active_message(
                    adapter=adapter,
                    target_type="person",
                    target_id=user_id,
                    message_chain=message_chain
                )
        except Exception as e:
            logger.error(f"Send message to user {user_id} failed: {e}")

# 主插件类
@register(name="RepoInsight", description="GitHub仓库智能分析插件", version="1.0.0", author="RepoInsight Team")
class RepoInsightPlugin(BasePlugin):
    
    def __init__(self, host: APIHost):
        super().__init__(host)
        self.state_manager = StateManager()
        self.github_client = GithubBotClient()
        self.message_handler = MessageHandler(self.state_manager, self.github_client)
        self.task_scheduler = TaskScheduler(self.state_manager, self.github_client, self)
    
    async def initialize(self):
        """异步初始化"""
        logger.info("RepoInsight plugin initializing...")
        await self.task_scheduler.start()
        logger.info("RepoInsight plugin initialized successfully")
    
    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        """处理私聊消息"""
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
        message = ctx.event.text_message
        user_id = str(ctx.event.sender_id)
        
        # 只处理@机器人或以/开头的消息
        if message.startswith('/') or '@' in message:
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