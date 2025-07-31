#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RepoInsight插件启动脚本
用于启动和管理插件服务
"""

import asyncio
import sys
import os
import json
import logging
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import RepoInsightPlugin, StateManager, GithubBotClient

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('repoinsight.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger('RepoInsight')

def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / 'config.json'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"配置文件未找到: {config_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"配置文件格式错误: {e}")
        return None

def check_dependencies():
    """检查依赖项"""
    required_modules = [
        'requests', 'aiohttp', 'pydantic', 'sqlite3'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"缺少依赖模块: {', '.join(missing_modules)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    return True

async def test_github_bot_connection(config):
    """测试GithubBot连接"""
    github_config = config.get('github_bot', {})
    base_url = github_config.get('base_url', 'http://github_bot_api:8000')
    
    client = GithubBotClient(base_url)
    
    print(f"正在测试GithubBot连接: {base_url}")
    try:
        is_healthy = await client.health_check()
        if is_healthy:
            print("✅ GithubBot连接正常")
            return True
        else:
            print("❌ GithubBot服务不可用")
            return False
    except Exception as e:
        print(f"❌ GithubBot连接失败: {e}")
        return False

def test_database_connection(config):
    """测试数据库连接"""
    db_config = config.get('database', {})
    db_path = db_config.get('path', 'repoinsight.db')
    
    print(f"正在测试数据库连接: {db_path}")
    try:
        state_manager = StateManager(db_path)
        # 尝试创建一个测试会话
        from main import UserSession
        test_session = UserSession('test_user')
        state_manager.save_session(test_session)
        retrieved_session = state_manager.get_session('test_user')
        
        if retrieved_session.user_id == 'test_user':
            print("✅ 数据库连接正常")
            return True
        else:
            print("❌ 数据库操作失败")
            return False
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

async def run_plugin_test():
    """运行插件测试"""
    print("\n=== 运行插件功能测试 ===")
    
    # 模拟LangBot上下文
    class MockContext:
        def __init__(self):
            self.messages = []
        
        async def reply(self, message):
            print(f"[回复] {message}")
            self.messages.append(('reply', message))
        
        async def send_message(self, message, user_id=None):
            print(f"[发送消息] {message} (用户: {user_id})")
            self.messages.append(('send', message, user_id))
    
    # 模拟消息事件
    class MockEvent:
        def __init__(self, user_id, message_text):
            self.user_id = user_id
            self.message_text = message_text
            self.is_group = False
            self.is_mentioned = True
    
    # 创建插件实例
    plugin = RepoInsightPlugin()
    await plugin.initialize()
    
    # 测试场景
    test_scenarios = [
        ("user1", "/help"),
        ("user1", "/repo"),
        ("user1", "https://github.com/microsoft/vscode"),
        ("user1", "/status"),
        ("user2", "什么是TypeScript？")
    ]
    
    for user_id, message in test_scenarios:
        print(f"\n--- 测试场景: 用户 {user_id} 发送 '{message}' ---")
        
        ctx = MockContext()
        event = MockEvent(user_id, message)
        
        try:
            await plugin.handle_message(ctx, event)
            print(f"✅ 处理成功，共 {len(ctx.messages)} 条响应")
        except Exception as e:
            print(f"❌ 处理失败: {e}")
    
    print("\n插件功能测试完成")

async def main():
    """主函数"""
    logger = setup_logging()
    
    print("=== RepoInsight插件启动器 ===")
    print("版本: 1.0.0")
    print("作者: Assistant")
    print()
    
    # 检查依赖
    print("1. 检查依赖项...")
    if not check_dependencies():
        return 1
    print("✅ 依赖项检查通过")
    
    # 加载配置
    print("\n2. 加载配置文件...")
    config = load_config()
    if not config:
        return 1
    print("✅ 配置文件加载成功")
    
    # 测试数据库连接
    print("\n3. 测试数据库连接...")
    if not test_database_connection(config):
        return 1
    
    # 测试GithubBot连接
    print("\n4. 测试GithubBot连接...")
    github_available = await test_github_bot_connection(config)
    if not github_available:
        print("⚠️  GithubBot服务不可用，部分功能可能受限")
    
    # 运行插件测试
    print("\n5. 运行插件功能测试...")
    try:
        await run_plugin_test()
        print("✅ 插件功能测试完成")
    except Exception as e:
        print(f"❌ 插件测试失败: {e}")
        logger.exception("插件测试异常")
        return 1
    
    print("\n=== 启动完成 ===")
    print("插件已准备就绪，可以在LangBot中使用")
    print("\n使用说明:")
    print("1. 发送 '/help' 查看帮助")
    print("2. 发送 '/repo' 开始分析GitHub仓库")
    print("3. 发送 '/status' 查看当前状态")
    print("4. 直接提问关于代码仓库的问题")
    
    return 0

if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n用户中断，退出程序")
        sys.exit(0)
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)