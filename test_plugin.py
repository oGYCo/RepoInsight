#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RepoInsight插件测试脚本
用于测试插件的基本功能和组件
"""

import asyncio
import unittest
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch

# 导入插件组件
from main import (
    UserState, TaskStatus, UserSession, StateManager,
    GithubBotClient, MessageHandler, TaskScheduler, RepoInsightPlugin
)

class TestUserSession(unittest.TestCase):
    """测试用户会话类"""
    
    def test_user_session_creation(self):
        """测试用户会话创建"""
        session = UserSession("user123")
        self.assertEqual(session.user_id, "user123")
        self.assertEqual(session.state, UserState.IDLE)
        self.assertIsNone(session.repo_url)
        self.assertIsNone(session.analysis_task_id)
    
    def test_user_session_serialization(self):
        """测试用户会话序列化"""
        session = UserSession(
            user_id="user123",
            state=UserState.ANALYZING,
            repo_url="https://github.com/test/repo",
            analysis_task_id="task123"
        )
        
        # 测试序列化
        data = session.to_dict()
        self.assertEqual(data['user_id'], "user123")
        self.assertEqual(data['state'], "analyzing")
        self.assertEqual(data['repo_url'], "https://github.com/test/repo")
        
        # 测试反序列化
        restored_session = UserSession.from_dict(data)
        self.assertEqual(restored_session.user_id, "user123")
        self.assertEqual(restored_session.state, UserState.ANALYZING)
        self.assertEqual(restored_session.repo_url, "https://github.com/test/repo")

class TestStateManager(unittest.TestCase):
    """测试状态管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.state_manager = StateManager(self.temp_db.name)
    
    def tearDown(self):
        """清理测试环境"""
        os.unlink(self.temp_db.name)
    
    def test_database_initialization(self):
        """测试数据库初始化"""
        # 数据库应该已经创建并初始化
        self.assertTrue(os.path.exists(self.temp_db.name))
    
    def test_session_persistence(self):
        """测试会话持久化"""
        # 创建并保存会话
        session = UserSession(
            user_id="user123",
            state=UserState.ANALYZING,
            repo_url="https://github.com/test/repo"
        )
        self.state_manager.save_session(session)
        
        # 获取会话
        retrieved_session = self.state_manager.get_session("user123")
        self.assertEqual(retrieved_session.user_id, "user123")
        self.assertEqual(retrieved_session.state, UserState.ANALYZING)
        self.assertEqual(retrieved_session.repo_url, "https://github.com/test/repo")
    
    def test_new_user_session(self):
        """测试新用户会话"""
        session = self.state_manager.get_session("new_user")
        self.assertEqual(session.user_id, "new_user")
        self.assertEqual(session.state, UserState.IDLE)

class TestGithubBotClient(unittest.TestCase):
    """测试GithubBot客户端"""
    
    def setUp(self):
        """设置测试环境"""
        self.client = GithubBotClient("http://test-server:8000")
    
    async def test_health_check_success(self):
        """测试健康检查成功"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"status": "healthy"})
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await self.client.health_check()
            self.assertTrue(result)
            mock_get.assert_called_once_with("http://test-server:8000/api/health")
    
    async def test_health_check_failure(self):
        """测试健康检查失败"""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await self.client.health_check()
            self.assertFalse(result)
    
    async def test_start_analysis_success(self):
        """测试开始分析成功"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "session_id": "session123",
                "task_id": "task123",
                "status": "pending"
            })
            mock_post.return_value.__aenter__.return_value = mock_response
            
            embedding_config = {"provider": "openai", "model": "text-embedding-ada-002"}
            result = await self.client.start_analysis("https://github.com/test/repo", embedding_config)
            self.assertEqual(result["session_id"], "session123")
            self.assertEqual(result["task_id"], "task123")
            mock_post.assert_called_once()

class TestMessageHandler(unittest.TestCase):
    """测试消息处理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.state_manager = StateManager(self.temp_db.name)
        self.github_client = Mock(spec=GithubBotClient)
        self.message_handler = MessageHandler(self.state_manager, self.github_client)
    
    def tearDown(self):
        """清理测试环境"""
        os.unlink(self.temp_db.name)
    
    def test_validate_github_url(self):
        """测试GitHub URL验证"""
        # 有效URL
        valid_urls = [
            "https://github.com/user/repo",
            "https://github.com/user-name/repo-name",
            "https://github.com/user.name/repo.name"
        ]
        for url in valid_urls:
            self.assertTrue(self.message_handler.validate_github_url(url))
        
        # 无效URL
        invalid_urls = [
            "http://github.com/user/repo",  # 不是https
            "https://gitlab.com/user/repo",  # 不是github
            "https://github.com/user",  # 缺少仓库名
            "not-a-url"
        ]
        for url in invalid_urls:
            self.assertFalse(self.message_handler.validate_github_url(url))
    
    async def test_handle_help_command(self):
        """测试帮助命令"""
        session = UserSession("user123")
        response = await self.message_handler.handle_command(session, "/help")
        self.assertIn("RepoInsight", response)
        self.assertIn("/repo", response)
        self.assertIn("/status", response)
    
    async def test_handle_repo_command(self):
        """测试仓库命令"""
        session = UserSession("user123")
        response = await self.message_handler.handle_command(session, "/repo")
        self.assertEqual(session.state, UserState.WAITING_FOR_REPO)
        self.assertIn("GitHub仓库URL", response)

def run_async_test(coro):
    """运行异步测试"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

class AsyncTestCase(unittest.TestCase):
    """异步测试基类"""
    
    def run_async(self, coro):
        """运行异步测试方法"""
        return run_async_test(coro)

class TestAsyncComponents(AsyncTestCase):
    """异步组件测试"""
    
    def test_github_client_health_check(self):
        """测试GitHub客户端健康检查"""
        client = GithubBotClient()
        
        async def test():
            # 模拟健康检查失败（因为没有真实服务器）
            result = await client.health_check()
            # 在没有真实服务器的情况下应该返回False
            self.assertFalse(result)
        
        self.run_async(test())

if __name__ == '__main__':
    print("开始运行RepoInsight插件测试...")
    
    # 运行同步测试
    print("\n=== 运行同步测试 ===")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUserSession)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestStateManager))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMessageHandler))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 运行异步测试
    print("\n=== 运行异步测试 ===")
    async_suite = unittest.TestLoader().loadTestsFromTestCase(TestAsyncComponents)
    async_result = runner.run(async_suite)
    
    # 输出测试结果
    total_tests = result.testsRun + async_result.testsRun
    total_failures = len(result.failures) + len(async_result.failures)
    total_errors = len(result.errors) + len(async_result.errors)
    
    print(f"\n=== 测试结果汇总 ===")
    print(f"总测试数: {total_tests}")
    print(f"成功: {total_tests - total_failures - total_errors}")
    print(f"失败: {total_failures}")
    print(f"错误: {total_errors}")
    
    if total_failures == 0 and total_errors == 0:
        print("\n🎉 所有测试通过！插件基本功能正常。")
    else:
        print("\n❌ 部分测试失败，请检查代码。")
    
    print("\n测试完成。")