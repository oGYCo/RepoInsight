#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RepoInsight插件独立测试脚本
用于在没有LangBot环境的情况下测试插件核心功能
"""

import asyncio
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 模拟LangBot的pkg.plugin模块
class MockEventContext:
    def __init__(self):
        self.event = None
        self.returns = {}
    
    def add_return(self, key, value):
        self.returns[key] = value
    
    def prevent_default(self):
        pass

class MockEvent:
    def __init__(self, text_message, sender_id):
        self.text_message = text_message
        self.sender_id = sender_id

class MockAPIHost:
    def get_platform_adapters(self):
        return []
    
    async def send_active_message(self, **kwargs):
        print(f"发送消息: {kwargs.get('message_chain', [])}")

class MockBasePlugin:
    def __init__(self, host):
        self.host = host

# 创建模拟模块
import types
pkg_module = types.ModuleType('pkg')
pkg_plugin_module = types.ModuleType('pkg.plugin')
pkg_plugin_context_module = types.ModuleType('pkg.plugin.context')
pkg_plugin_events_module = types.ModuleType('pkg.plugin.events')
pkg_platform_module = types.ModuleType('pkg.platform')
pkg_platform_types_module = types.ModuleType('pkg.platform.types')

# 添加必要的类和函数
pkg_plugin_context_module.BasePlugin = MockBasePlugin
pkg_plugin_context_module.APIHost = MockAPIHost
pkg_plugin_context_module.EventContext = MockEventContext
pkg_plugin_context_module.register = lambda **kwargs: lambda cls: cls
pkg_plugin_context_module.handler = lambda event_type: lambda func: func

class PersonNormalMessageReceived:
    pass

class GroupNormalMessageReceived:
    pass

pkg_plugin_events_module.PersonNormalMessageReceived = PersonNormalMessageReceived
pkg_plugin_events_module.GroupNormalMessageReceived = GroupNormalMessageReceived

class MessageChain:
    def __init__(self, items):
        self.items = items

class Plain:
    def __init__(self, text):
        self.text = text

pkg_platform_types_module.MessageChain = MessageChain
pkg_platform_types_module.Plain = Plain

# 注册模块
sys.modules['pkg'] = pkg_module
sys.modules['pkg.plugin'] = pkg_plugin_module
sys.modules['pkg.plugin.context'] = pkg_plugin_context_module
sys.modules['pkg.plugin.events'] = pkg_plugin_events_module
sys.modules['pkg.platform'] = pkg_platform_module
sys.modules['pkg.platform.types'] = pkg_platform_types_module

# 现在可以导入主模块
from main import (
    UserState, UserSession, StateManager, 
    GithubBotClient, MessageHandler, ConfigManager
)

async def test_basic_functionality():
    """测试基本功能"""
    print("=== RepoInsight 插件独立测试 ===")
    
    # 测试配置管理器
    print("\n1. 测试配置管理器...")
    config = ConfigManager()
    base_url = config.get('github_bot_api.base_url', 'http://github_bot_api:8000')
    print(f"   GithubBot API URL: {base_url}")
    
    # 测试状态管理器
    print("\n2. 测试状态管理器...")
    state_manager = StateManager(":memory:")  # 使用内存数据库
    
    # 创建测试会话
    session = UserSession("test_user")
    print(f"   创建会话: {session.user_id}, 状态: {session.state.value}")
    
    # 保存和获取会话
    state_manager.save_session(session)
    retrieved_session = state_manager.get_session("test_user")
    print(f"   获取会话: {retrieved_session.user_id}, 状态: {retrieved_session.state.value}")
    
    # 测试GithubBot客户端
    print("\n3. 测试GithubBot客户端...")
    github_client = GithubBotClient(base_url)
    print(f"   客户端创建成功，目标URL: {github_client.base_url}")
    
    # 测试健康检查（可能会失败，这是正常的）
    try:
        health_status = await github_client.health_check()
        print(f"   健康检查结果: {health_status}")
    except Exception as e:
        print(f"   健康检查失败（预期的）: {e}")
    
    # 测试消息处理器
    print("\n4. 测试消息处理器...")
    message_handler = MessageHandler(state_manager, github_client)
    
    # 测试URL验证
    valid_url = "https://github.com/microsoft/vscode"
    invalid_url = "not-a-url"
    
    print(f"   验证有效URL '{valid_url}': {message_handler.validate_github_url(valid_url)}")
    print(f"   验证无效URL '{invalid_url}': {message_handler.validate_github_url(invalid_url)}")
    
    # 测试命令处理
    ctx = MockEventContext()
    ctx.event = MockEvent("/help", "test_user")
    
    try:
        response = await message_handler.handle(ctx, "/help", "test_user")
        print(f"   帮助命令响应: {response[:100]}...")
    except Exception as e:
        print(f"   命令处理测试失败: {e}")
    
    print("\n=== 测试完成 ===")
    print("\n注意：")
    print("- 这个插件需要在LangBot环境中运行")
    print("- 需要GithubBot服务运行在配置的URL上")
    print("- 独立测试只能验证基本的类和方法功能")

if __name__ == "__main__":
    asyncio.run(test_basic_functionality())