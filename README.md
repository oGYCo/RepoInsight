# RepoInsight - GitHub仓库智能分析插件

## 简介

RepoInsight 是一个为 LangBot 设计的智能GitHub仓库分析插件。它能够深度分析GitHub仓库的代码结构、功能特性，并提供智能问答服务，帮助开发者快速理解和探索代码库。

## 核心功能

### 🔍 智能仓库分析
- **自动代码解析**：深度分析仓库结构、依赖关系、核心模块
- **技术栈识别**：自动识别项目使用的编程语言、框架和工具
- **架构洞察**：提供项目架构概览和设计模式分析

### 💬 智能问答系统
- **代码理解**：回答关于代码功能、实现逻辑的问题
- **最佳实践**：提供代码优化建议和最佳实践指导
- **快速导航**：帮助快速定位特定功能或模块

### 🚀 异步处理机制
- **非阻塞分析**：后台异步处理，不影响用户其他操作
- **实时通知**：分析完成后主动推送结果
- **并发支持**：支持多用户同时使用

## 安装方法

### 方法一：通过LangBot插件管理器安装

1. 在LangBot中发送以下命令：
```
!plugin get https://github.com/your-username/RepoInsight
```

### 方法二：手动安装

1. 将插件文件下载到LangBot的`plugins`目录
2. 重启LangBot或重新加载插件

## 使用指南

### 基本命令

| 命令 | 功能 | 示例 |
|------|------|------|
| `/repo` | 开始分析新的GitHub仓库 | `/repo` |
| `/status` | 查看当前分析状态 | `/status` |
| `/exit` | 退出当前会话 | `/exit` |
| `/help` | 显示帮助信息 | `/help` |

### 使用流程

1. **开始分析**
   ```
   用户: /repo
   机器人: 请发送要分析的GitHub仓库URL（例如：https://github.com/user/repo）
   ```

2. **提供仓库URL**
   ```
   用户: https://github.com/microsoft/vscode
   机器人: 开始分析仓库：https://github.com/microsoft/vscode
           任务ID：task_12345
           请稍候，分析完成后会自动通知您。
   ```

3. **等待分析完成**
   ```
   机器人: 仓库分析完成！
           仓库：https://github.com/microsoft/vscode
           现在可以开始提问了。
   ```

4. **开始提问**
   ```
   用户: 这个项目的主要架构是什么？
   机器人: 正在处理您的问题：这个项目的主要架构是什么？
           任务ID：query_67890
           请稍候，处理完成后会自动回复您。
   ```

### 支持的问题类型

- **架构相关**："这个项目的整体架构是什么？"
- **功能询问**："如何实现用户认证功能？"
- **代码定位**："处理文件上传的代码在哪里？"
- **技术选型**："这个项目使用了哪些主要技术？"
- **最佳实践**："如何优化这个模块的性能？"

## 配置说明

插件配置文件 `config.json` 包含以下选项：

```json
{
  "github_bot": {
    "base_url": "http://localhost:8000",  // GithubBot服务地址
    "timeout": 30,                        // 请求超时时间
    "retry_attempts": 3,                  // 重试次数
    "retry_delay": 5                      // 重试延迟
  },
  "database": {
    "path": "repo_insight.db",            // 数据库文件路径
    "cleanup_hours": 24                   // 会话清理时间
  },
  "polling": {
    "analysis_interval": 10,              // 分析状态轮询间隔
    "query_interval": 5,                  // 查询结果轮询间隔
    "cleanup_interval": 3600              // 清理任务间隔
  }
}
```

## 技术架构

### 核心组件

1. **RepoInsightPlugin**：主插件类，处理LangBot事件
2. **StateManager**：用户状态管理，基于SQLite持久化
3. **GithubBotClient**：与GithubBot服务的HTTP客户端
4. **MessageHandler**：消息处理和指令解析
5. **TaskScheduler**：异步任务调度和状态轮询

### 状态机设计

```
IDLE → WAITING_FOR_REPO → ANALYZING → READY_FOR_QUESTIONS → WAITING_FOR_ANSWER
  ↑                                           ↓                        ↓
  └─────────────────── EXIT ←─────────────────┴────────────────────────┘
```

### 异步处理流程

1. **仓库分析**：用户提交URL → 后台异步分析 → 完成后主动通知
2. **问题处理**：用户提问 → 后台异步处理 → 完成后主动回复
3. **状态轮询**：定期检查任务状态，及时更新用户状态

## 依赖服务

### GithubBot服务

插件需要配合GithubBot服务使用，该服务提供以下API：

- `GET /health` - 健康检查
- `POST /analyze` - 开始仓库分析
- `GET /analyze/{task_id}/status` - 获取分析状态
- `POST /query` - 提交问题
- `GET /query/{task_id}/result` - 获取查询结果

### 环境要求

- Python 3.8+
- LangBot 框架
- SQLite 数据库
- 网络连接（访问GitHub和GithubBot服务）

## 开发指南

### 项目结构

```
RepoInsight/
├── main.py              # 主插件文件
├── manifest.yaml        # 插件清单
├── requirements.txt     # Python依赖
├── config.json         # 配置文件
├── README.md           # 说明文档
└── repo_insight.db     # SQLite数据库（运行时生成）
```

### 扩展开发

1. **添加新指令**：在`MessageHandler.handle_command`中添加新的指令处理逻辑
2. **自定义状态**：扩展`UserState`枚举，添加新的用户状态
3. **增强API**：在`GithubBotClient`中添加新的API调用方法
4. **优化轮询**：调整`TaskScheduler`中的轮询策略和频率

## 故障排除

### 常见问题

1. **GithubBot服务不可用**
   - 检查`config.json`中的`base_url`配置
   - 确认GithubBot服务正在运行
   - 检查网络连接

2. **分析失败**
   - 确认GitHub仓库URL格式正确
   - 检查仓库是否为公开仓库
   - 查看GithubBot服务日志

3. **数据库错误**
   - 检查SQLite数据库文件权限
   - 确认磁盘空间充足
   - 重新初始化数据库

### 日志调试

插件使用Python标准logging模块，可以通过以下方式查看详细日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 更新日志

### v1.0.0 (2024-01-XX)
- 初始版本发布
- 支持GitHub仓库分析
- 智能问答功能
- 异步处理机制
- 用户状态管理

## 贡献指南

欢迎提交Issue和Pull Request来改进这个插件！

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

**RepoInsight** - 让代码理解变得简单！
