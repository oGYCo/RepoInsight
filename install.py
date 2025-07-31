#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RepoInsight插件安装脚本
自动安装依赖并配置插件环境
"""

import os
import sys
import subprocess
import json
import shutil
from pathlib import Path

def print_banner():
    """打印安装横幅"""
    print("="*60)
    print("    RepoInsight LangBot Plugin Installer")
    print("    智能GitHub仓库分析插件安装器")
    print("="*60)
    print()

def check_python_version():
    """检查Python版本"""
    print("检查Python版本...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python版本过低: {version.major}.{version.minor}")
        print("需要Python 3.8或更高版本")
        return False
    
    print(f"✅ Python版本: {version.major}.{version.minor}.{version.micro}")
    return True

def check_pip():
    """检查pip是否可用"""
    print("检查pip...")
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ pip可用: {result.stdout.strip()}")
            return True
        else:
            print("❌ pip不可用")
            return False
    except Exception as e:
        print(f"❌ pip检查失败: {e}")
        return False

def install_dependencies():
    """安装Python依赖"""
    print("\n安装Python依赖...")
    
    requirements_file = Path(__file__).parent / 'requirements.txt'
    if not requirements_file.exists():
        print("❌ requirements.txt文件不存在")
        return False
    
    try:
        # 升级pip
        print("升级pip...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], 
                      check=True, capture_output=True)
        
        # 安装依赖
        print("安装项目依赖...")
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print("✅ 依赖安装成功")
            return True
        else:
            print(f"❌ 依赖安装失败: {result.stderr}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 安装过程出错: {e}")
        return False

def setup_database():
    """设置数据库"""
    print("\n设置数据库...")
    
    try:
        # 导入并初始化数据库
        sys.path.insert(0, str(Path(__file__).parent))
        from main import StateManager
        
        db_path = Path(__file__).parent / 'repoinsight.db'
        state_manager = StateManager(str(db_path))
        
        print(f"✅ 数据库初始化成功: {db_path}")
        return True
        
    except Exception as e:
        print(f"❌ 数据库设置失败: {e}")
        return False

def create_config_if_needed():
    """如果需要，创建配置文件"""
    print("\n检查配置文件...")
    
    config_path = Path(__file__).parent / 'config.json'
    if config_path.exists():
        print("✅ 配置文件已存在")
        return True
    
    print("创建默认配置文件...")
    try:
        default_config = {
            "github_bot": {
                "base_url": "http://localhost:8000",
                "timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 1
            },
            "database": {
                "path": "repoinsight.db",
                "cleanup_hours": 24
            },
            "polling": {
                "analysis_interval": 10,
                "query_interval": 5,
                "cleanup_interval": 3600
            },
            "limits": {
                "max_question_length": 1000,
                "max_sessions_per_user": 5,
                "session_timeout_hours": 2
            },
            "features": {
                "enable_group_chat": True,
                "enable_private_chat": True,
                "require_mention_in_group": True,
                "auto_cleanup": True
            }
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 配置文件创建成功: {config_path}")
        return True
        
    except Exception as e:
        print(f"❌ 配置文件创建失败: {e}")
        return False

def verify_installation():
    """验证安装"""
    print("\n验证安装...")
    
    try:
        # 尝试导入主模块
        sys.path.insert(0, str(Path(__file__).parent))
        from main import RepoInsightPlugin
        
        print("✅ 主模块导入成功")
        
        # 检查必要文件
        required_files = [
            'main.py',
            'manifest.yaml',
            'config.json',
            'requirements.txt',
            'README.md'
        ]
        
        base_path = Path(__file__).parent
        missing_files = []
        
        for file_name in required_files:
            file_path = base_path / file_name
            if not file_path.exists():
                missing_files.append(file_name)
        
        if missing_files:
            print(f"❌ 缺少文件: {', '.join(missing_files)}")
            return False
        
        print("✅ 所有必要文件存在")
        return True
        
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

def print_next_steps():
    """打印后续步骤"""
    print("\n" + "="*60)
    print("🎉 安装完成！")
    print("="*60)
    print()
    print("后续步骤:")
    print()
    print("1. 启动GithubBot服务 (如果还没有启动):")
    print("   请确保GithubBot API服务在 http://localhost:8000 运行")
    print()
    print("2. 测试插件:")
    print("   python run.py")
    print()
    print("3. 在LangBot中安装插件:")
    print("   - 将此文件夹复制到LangBot的plugins目录")
    print("   - 重启LangBot")
    print("   - 发送 '/help' 测试插件")
    print()
    print("4. 配置调整 (可选):")
    print("   编辑 config.json 文件调整插件设置")
    print()
    print("使用说明:")
    print("- 发送 '/repo' 开始分析GitHub仓库")
    print("- 发送 '/status' 查看当前状态")
    print("- 发送 '/help' 查看完整帮助")
    print("- 直接提问关于代码仓库的问题")
    print()
    print("如有问题，请查看 README.md 或运行测试脚本")
    print("测试脚本: python test_plugin.py")
    print()

def main():
    """主安装流程"""
    print_banner()
    
    # 检查系统要求
    if not check_python_version():
        return 1
    
    if not check_pip():
        return 1
    
    # 安装依赖
    if not install_dependencies():
        print("\n安装失败，请检查错误信息")
        return 1
    
    # 设置数据库
    if not setup_database():
        print("\n数据库设置失败")
        return 1
    
    # 创建配置文件
    if not create_config_if_needed():
        print("\n配置文件创建失败")
        return 1
    
    # 验证安装
    if not verify_installation():
        print("\n安装验证失败")
        return 1
    
    # 打印后续步骤
    print_next_steps()
    
    return 0

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n用户中断安装")
        sys.exit(1)
    except Exception as e:
        print(f"\n安装过程出现异常: {e}")
        sys.exit(1)