# RepoInsight 插件开发文档

## 1. 项目概述
### 1.1 项目目标
开发一个名为RepoInsight的LangBot插件，实现微信用户通过特定指令与后端 GithubBot 服务交互。插件使得用户能便捷地提交 GitHub 仓库地址进行分析，并在分析完成后，通过对话方式进行仓库内容的问答。

### 1.2 核心功能
- **指令式交互**: 用户通过 /repo, /exit 等指令控制插件行为。
- **仓库分析模式启动**：用户通过特定指令进入仓库分析模式
- **仓库分析请求**：解析用户发送的仓库地址，调用GithubBot API进行仓库分析
- **异步任务处理**: 提交仓库分析请求后，插件能异步跟踪 `GithubBot` 的处理进度。
- **主动状态通知**: 仓库分析开始和完成时，插件主动向用户发送通知，提升体验。
- **上下文问答**: 在分析完成后，插件维持一个问答会话，将用户问题转发给 `GithubBot` 并返回结果。
- **持久化会话**: 稳健地管理用户状态和其与 `GithubBot` 的会话ID，即使用户长时间无操作或插件重启也不丢失。

### 1.3. 核心流程与用户体验

1.  **启动**: 用户发送 `/repo` 或 `/仓库分析`。
    -   **插件响应**: “您好！已进入仓库分析模式。请直接发送一个 GitHub 仓库的 URL (例如: `https://github.com/owner/repo`)。随时可以通过 `/exit` 退出。”

2.  **提交仓库**: 用户发送一个 GitHub 仓库链接。
    -   **插件响应 (开始分析)**: 立即回复：“✅ 已收到仓库链接，正在请求分析，请稍候... 这可能需要几分钟时间。”
    -   **后台操作**: 插件调用 `GithubBot` 的 `/analyze` 接口。

3.  **分析进行中**:
    -   **后台操作**: 插件通过轮询 `GithubBot` 的 `/status` 接口来跟踪进度。
    -   **(可选优化)** 如果分析时间很长，可以考虑每隔几分钟给用户一个“仍在分析中”的提示，防止用户以为进程已死。

4.  **分析完成**:
    -   **插件响应 (主动通知)**: “🎉 好消息！仓库 `owner/repo` 已分析完成。现在您可以就这个仓库向我提问了。”
    -   **后台操作**: 插件更新用户状态为 `ready_for_query`。

5.  **问答交互**: 用户发送问题，如“代码里用到了哪些数据库？”
    -   **后台操作**: 插件调用 `GithubBot` 的 `/query` 接口。
    -   **插件响应**: 将 `GithubBot` 返回的答案直接回复给用户。

6.  **退出**: 用户发送 `/exit` 或 `/退出`。
    -   **插件响应**: “已退出仓库分析模式。感谢使用！”
    -   **后台操作**: 清理当前用户的会话状态。

## 2. 技术架构
### 2.1 系统架构图
```
+------------+     +-----------------+     +-----------------------+     +--------------------+
| 微信用户    | <-> | LangBot Core    | <-> | RepoInsight Plugin    | <-> | GithubBot API 服务 |
+------------+     +-----------------+     +-----------------------+     +--------------------+
                                                  |
                                                  |
                                       +------------------------+
                                       |   持久化存储 (SQLite)    |
                                       | (管理用户状态与会话ID)    |
                                       +------------------------+
```

### 2.2 核心组件
1. **插件主类**：`RepoInsightPlugin`: 插件主入口，负责注册指令、接收和分发消息。
2. **API客户端**：`GithubBotClient`: `GithubBot` API 的客户端，封装了对 `/analyze`, `/status`, `/query` 等接口的 HTTP 请求，并处理网络异常。
3. **消息处理器**：`MessageHandler`: 消息处理器，根据用户的当前状态（`state`）决定如何处理消息（是解析为指令、仓库URL还是普通问题）。
4. **状态管理器**：`StateManager`: 状态管理器，负责查询和更新用户的状态。**状态和会话ID必须持久化存储**。
5. **TaskScheduler**: 一个后台任务调度器（如使用 `apscheduler`），用于定期轮询分析状态，并在分析完成后触发对用户的通知。

### 2.3 用户状态管理 (State Machine)
用户的状态是整个交互的核心。必须为每个用户独立维护状态。

| 状态 (State)        | 触发条件                | 行为                            | 下一状态           |
| :----------------- | :---------------------- | :------------------------------ | :----------------- |
| `idle` (初始状态)   | 用户发送 `/repo`        | 回复欢迎语                      | `waiting_for_repo` |
| `waiting_for_repo` | 用户发送合法 GitHub URL | 调用 `/analyze`，回复“开始分析” | `analyzing`        |
| `waiting_for_repo` | 用户发送无效消息        | 提示需要输入仓库URL             | `waiting_for_repo` |
| `analyzing`        | 后台任务发现分析完成    | 主动通知用户“分析完毕”          | `ready_for_query`  |
| `analyzing`        | 用户发送任何消息        | 回复“正在分析中，请稍候...”     | `analyzing`        |
| `ready_for_query`  | 用户发送问题            | 调用 `/query` 并返回答案        | `ready_for_query`  |
| *任何状态*          | 用户发送 `/exit`        | 回复“已退出”，清理会话          | `idle`             |
| *任何状态*          | 用户发送 `/help`        | 显示帮助信息                    | *保持当前状态*     |

## 3. 详细需求分析
### 3.1 功能需求

#### 3.1.1 指令系统
- **启动分析模式**：`/repo` 或 `/仓库分析`
- **退出分析模式**：`/exit` 或 `/退出`
- **查看帮助**：`/help` 或 `/帮助`
- **查看状态**：`/status` 或 `/状态`

#### 3.1.2 仓库分析流程
1. 用户发送仓库URL（支持GitHub）
2. 插件验证URL格式
3. 调用GithubBot API开始分析
4. 实时反馈分析进度
5. 分析完成后通知用户

#### 3.1.3 问答功能
1. 用户发送关于仓库的问题
2. 插件调用GithubBot查询API
3. 返回AI生成的答案
4. 支持上下文对话

#### 3.1.4 会话管理
1. 维护用户状态（空闲、分析中、问答中）
2. 管理用户与session_id的映射
3. 支持多用户并发使用
4. 会话超时处理

### 3.2 非功能需求

#### 3.2.1 性能要求
- 支持并发用户数：100+
- API响应时间：< 3秒
- 消息处理延迟：< 1秒

#### 3.2.2 可靠性要求
- 异常处理覆盖率：100%
- 服务可用性：99.9%
- 数据持久化：会话信息本地存储

#### 3.2.3 安全要求
- 输入验证：URL格式验证
- 权限控制：用户权限管理
- 数据保护：敏感信息加密存储

## 4 GithubBot 提供的API接口
### 🌐 API基础信息
- 基础URL : http://localhost:8000/api/v1
### 4.1 🏠 系统接口 根路径
- GET /
- 功能 : 返回API基本信息
- 响应 : 服务名称、版本、文档链接 健康检查
- GET /health
- 功能 : 检查服务健康状态
- 响应 : 服务状态、数据库连接状态、时间戳等
### 4.2 📦 仓库分析接口 (/api/v1/repos) 
#### 启动仓库分析
- POST /api/v1/repos/analyze
- 功能 : 提交仓库分析任务
- 请求体 :
```json
{
  "repo_url": "https://github.com/user/repo",
  "embedding_config": {
    "provider": "openai|azure|huggingface|ollama|google|qwen",
    "model_name": "text-embedding-ada-002",
    "api_key": "your-api-key",
    "api_base": "optional",
    "extra_params": {}
  }
}
```
- *插件需要管理 `embedding_config` 的配置，可以设置为固定值或允许用户通过指令修改。*
- GithubBot的响应例子 : 
```json
{
    "session_id":"4adb1c93-7e80-4a58-904c-d637ab0bb220",
    "task_id":"b5244c8c-e2bf-4701-98c3-ae8a5f680b92",
    "status":"queued",
    "message":"Repository analysis has been queued for processing"
}
```

#### 查询分析状态
- GET /api/v1/repos/status/{session_id}
- 功能 : 获取仓库分析进度和状态
- GithubBot的响应例子：
```json
{
    "session_id":"4adb1c93-7e80-4a58-904c-d637ab0bb220",
    "status":"success",
    "repository_url":"https://github.com/oGYCo/GithubBot",
    "repository_name":"GithubBot",
    "repository_owner":"oGYCo",
    "total_files":36,
    "processed_files":28,
    "total_chunks":324,
    "indexed_chunks":324,
    "created_at":"2025-07-31T03:50:40.655135+00:00",
    "started_at":"2025-07-31T03:50:40.664749+00:00",
    "completed_at":"2025-07-31T03:51:06.264323+00:00",
    "error_message":null
}
```
*当 `status` 变为 `success` 时，表示分析完成。*

#### 取消分析任务
- POST /api/v1/repos/analyze/{session_id}/cancel
- 功能 : 停止正在进行的仓库分析任务
- 响应 : 取消状态确认

### 4.3 问答接口
#### 提交查询请求
- POST /api/v1/repos/query
- 功能 : 对已分析的仓库进行问答查询
- 请求体 :
  ```json
  {
    "session_id": 
    "analysis-session-id",
    "question": "What is the main 
    purpose of this repository?",
    "generation_mode": "service|
    plugin",
    "llm_config": {
      "provider": "openai|azure|
      huggingface|ollama|deepseek|
      google|qwen",
      "model_name": "gpt-3.5-turbo",
      "api_key": "your-api-key",
      "temperature": 0.7,
      "max_tokens": 1000
    }
  }
  ```
**问答的时候使用的session_id就是前面分析仓库返回的session_id**
**插件需要管理 `llm_config` 的配置。**

- GithubBot的响应例子:
```json
{
    "session_id":"bb7e5849-3086-4b94-9439-7a5de259546d",
    "task_id":"bb7e5849-3086-4b94-9439-7a5de259546d",
    "status":"queued",
    "message":"Query task has been queued for processing"
}
```
**这个返回的session_id就是问答query的seesion_id了，跟分析仓库的那个session_id不一样**

#### 查询任务状态
- GET /api/v1/repos/query/status/{session_id}
- 功能 : 获取查询任务的基本状态信息（不包含结果数据，适合频繁轮询）
- 适用场景 : 轮询检查任务是否完成，获取简洁的状态信息
- 响应 : 轻量级的状态信息
```json
{
  "session_id":"51a9871d-8d55-4077-b2c1-cf1893b79183",
  "status":"success",
  "ready":true,
  "successful":true,
  "message":"Task completed successfully"
}
```
#### 获取查询结果
- GET /api/v1/repos/query/result/{session_id}
- 功能 : 获取已完成查询任务的最终结果
- 响应 : 完整的QueryResponse数据
```json
{
  "answer":"根据提供的上下文信息，我将从功能、架构和关键组件等方面简单介绍该 GitHub 仓库问答机器人项目，并引用相关文件和代码行进行说明。\n\n---\n\n### 一、项目概述\n\n该项目是一个 **GitHub 仓库问答机器人**，其主要目标是通过 AI 技术帮助开发者与代码库进行自然语言交互。它可以自动学习一个 GitHub 仓库的全部代码和文档，并通过一个智能聊天机器人回答关于该仓库的任何问题。\n\n> 项目仍在开发中，尚未完全可用 [README_ZH.md (行 61)](文档 8)\n\n---\n\n### 二、核心功能\n\n1. **智能代码问答（RAG）**\n   - 基于检索增强生成（RAG）技术，提供精准的、上下文感知的代码解释和建议。\n   - 支持多种 LLM（语言模型）和 Embedding 模型提供商，如 OpenAI、Azure、HuggingFace、Ollama 等。\n   - 支持插件模式或服务端生成答案两种模式。\n\n2. **全自动处理**\n   - 提供一个 GitHub 仓库 URL 后，系统会自动完成代码克隆、解析、分块、向量化和索引。\n\n3. **高度可扩展**\n   - 可轻松更换或扩展 LLM、Embedding 模型和向量数据库。\n   - 支持多种模型提供商，如 OpenAI、Azure、Cohere、HuggingFace 等。\n\n4. **混合搜索**\n   - 结合向量搜索和 BM25 关键字搜索，确保在不同类型的查询下都能获得最佳的上下文检索效果。\n\n5. **异步任务处理**\n   - 使用 Celery 和 Redis 处理耗时的仓库索引任务，确保 API 服务的响应速度和稳定性。\n\n6. **一键部署**\n   - 提供完整的 Docker-Compose 配置，一行命令即可启动所有服务（API、Worker、数据库等）。\n\n> 详见 [README_ZH.md (行 81)](文档 5)\n\n---\n\n### 三、核心架构与模块\n\n#### 1. 核心分析服务（RepoInsight-Service）\n\n这是一个独立的 **FastAPI 应用**，是整个项目的大脑，负责所有的计算和数据处理。\n\n- **功能**：接收用户请求，启动分析任务，异步处理，返回任务状态。\n- **实现**：`src/api/v1/endpoints/repositories.py` 中定义了 `/analyze` 接口，接收仓库 URL 和配置后生成唯一 session_id，并将任务推送到 Celery 队列进行异步处理。\n- **示例代码**：\n  ```python\n  @router.post(\"/analyze\")\n  async def analyze(req: RepoAnalyzeRequest):\n      ...\n      session_id = str(uuid.uuid4())\n      task_id = await task_queue.push_query_task(session_id, req)\n      ...\n  ```\n\n> 详见 [architecture.md (行 1)](文档 1) 和 [repositories.py (行 161)](文档 2)\n\n---\n\n#### 2. 后台任务处理（Worker）\n\n- **功能**：处理耗时操作如仓库克隆、代码解析、向量化等。\n- **实现**：`src/worker/tasks.py` 定义了 `process_repository_task`，由 Celery 异步执行。\n- **示例代码**：\n  ```python\n  @celery_app.task(bind=True, name=\"process_repository\")\n  def process_repository_task(session_id: str, req: dict):\n      ...\n      if success:\n          return {\"success\": True, \"session_id\": session_id, \"message\": \"...\"}\n  ```\n\n> 详见 [architecture.md (行 181)](文档 3) 和 [tasks.py (行 41)](文档 7)\n\n---\n\n#### 3. 向量数据库适配器\n\n- **功能**：封装与 ChromaDB 的交互，提供标准接口如“创建集合”、“添加文档”、“查询向量”。\n- **实现**：`src/services/vector_store.py`\n- **作用**：使上层服务无需关心 ChromaDB 的具体实现细节。\n\n> 详见 [architecture.md (行 181)](文档 3)\n\n---\n\n#### 4. 工具库（Utils）\n\n- **功能**：提供通用工具函数，如 Git 操作、文件解析等。\n- **实现**：\n  - `src/utils/git_helper.py` 负责克隆仓库。\n  - `src/utils/file_parser.py` 负责解析文件。\n- **示例代码**：\n  ```python\n  def get_repository_list() -> list:\n      ...\n      return repositories\n  ```\n\n> 详见 [architecture.md (行 181)](文档 3) 和 [git_helper.py (行 261)](文档 9)\n\n---\n\n#### 5. 数据模型与请求/响应结构\n\n- **功能**：定义 API 请求和响应的数据结构。\n- **实现**：`src/schemas/repository.py`\n- **包含枚举类型**：\n  - `LLMProvider`：LLM 模型提供商\n  - `EmbeddingProvider`：Embedding 模型提供商\n  - `GenerationMode`：生成模式（服务端或插件）\n  - `TaskStatus`：任务状态（pending, processing, success 等）\n\n> 详见 [repository.py (行 1)](文档 4)\n\n---\n\n### 四、模块间关系图（逻辑）\n\n```\n[用户请求] → [FastAPI API] → [生成 session_id] → [推送到 Celery 队列]\n                                   ↓\n                          [Worker 异步处理任务]\n                                   ↓\n                    [Git 克隆仓库] → [解析文件] → [向量化并存入 ChromaDB]\n                                   ↓\n                             [任务状态更新]\n                                   ↓\n                      [用户可通过 session_id 查询结果]\n```\n\n---\n\n### 五、总结\n\n该项目是一个结构清晰、模块化良好、支持异步处理的 GitHub 仓库问答机器人系统。它结合了 RAG 技术、向量数据库、多种模型支持和高度可扩展性，具备良好的工程实践基础。目前仍在开发中，但已有完整的架构设计和部分实现。",
  "retrieved_context":[
    {"id":"chunk_4adb1c93-7e80-4a58-904c-d637ab0bb220_21","content":"文件路径: architecture.md\n\n### **项目:GitHub 仓库问答机器人 架构**\n\n-----\n\n### **第一部分:核心分析服务 (RepoInsight-Service)**\n\n这是一个独立的 FastAPI 应用,是整个项目的大脑,负责所有的计算和数据处理","file_path":"architecture.md","start_line":1,"score":0.01639344262295082,"metadata":{"chunk_index":21,"content":"文件路径: architecture.md\n\n### **项目:GitHub 仓库问答机器人 架构**\n\n-----\n\n### **第一部分:核心分析服务 (RepoInsight-Service)**\n\n这是一个独立的 FastAPI 应用,是整个项目的大脑,负责所有的计算和数据处理","file_path":"architecture.md","language":"markdown","start_line":1,"file_type":"document","source":"architecture.md"}},{"id":"chunk_4adb1c93-7e80-4a58-904c-d637ab0bb220_315","content":"if req.llm_config:\n        logger.info(f\"🤖 [LLM配置] 提供商: {req.llm_config.provider}, 模型: {req.llm_config.model_name}\")\n\n    # 生成唯一的session_id\n    session_id = str(uuid.uuid4())\n    logger.info(f\"🆔 [任务会话] 生成查询任务会话ID: {session_id}\")\n\n    # 将任务推送到Celery\n    logger.info(f\"📤 [任务队列] 正在推送查询任务到队列...\")\n    task_id = await task_queue.push_query_task(session_id, req)\n    logger.info(f\"✅ [任务队列] 查询任务推送成功 - 任务ID: {task_id}\")\n\n    response = {\n        \"session_id\": session_id,\n        \"task_id\": task_id,\n        \"status\": \"queued\",\n        \"message\": \"Query task has been queued for processing\"\n    }\n\n    logger.info(f\"🎉 [查询响应] 查询请求处理完成 - 任务会话ID: {session_id}\")\n    return response\n\n@router.post(\"/analyze/{session_id}/cancel\")\nasync def cancel_analysis(session_id: str):\n    \"\"\"\n    停止仓库分析任务\n    \"\"\"\n    try:\n        logger.info(f\"🛑 [停止请求] 收到停止仓库分析请求 - 会话ID: {session_id}\")","file_path":"src/api/v1/endpoints/repositories.py","start_line":161,"score":0.016129032258064516,"metadata":{"start_line":161,"source":"src/api/v1/endpoints/repositories.py","chunk_index":315,"content":"if req.llm_config:\n        logger.info(f\"🤖 [LLM配置] 提供商: {req.llm_config.provider}, 模型: {req.llm_config.model_name}\")\n\n    # 生成唯一的session_id\n    session_id = str(uuid.uuid4())\n    logger.info(f\"🆔 [任务会话] 生成查询任务会话ID: {session_id}\")\n\n    # 将任务推送到Celery\n    logger.info(f\"📤 [任务队列] 正在推送查询任务到队列...\")\n    task_id = await task_queue.push_query_task(session_id, req)\n    logger.info(f\"✅ [任务队列] 查询任务推送成功 - 任务ID: {task_id}\")\n\n    response = {\n        \"session_id\": session_id,\n        \"task_id\": task_id,\n        \"status\": \"queued\",\n        \"message\": \"Query task has been queued for processing\"\n    }\n\n    logger.info(f\"🎉 [查询响应] 查询请求处理完成 - 任务会话ID: {session_id}\")\n    return response\n\n@router.post(\"/analyze/{session_id}/cancel\")\nasync def cancel_analysis(session_id: str):\n    \"\"\"\n    停止仓库分析任务\n    \"\"\"\n    try:\n        logger.info(f\"🛑 [停止请求] 收到停止仓库分析请求 - 会话ID: {session_id}\")","file_path":"src/api/v1/endpoints/repositories.py","file_type":"code","language":"python"}},{"id":"chunk_4adb1c93-7e80-4a58-904c-d637ab0bb220_30","content":"* **`src/services/vector_store.py`**: **【向量数据库适配器】** 封装了所有与 ChromaDB 的直接交互,提供如“创建集合”、“添加文档”、“查询向量”等标准接口,使上层服务无需关心 ChromaDB 的具体实现细节。\n\n  * **`src/utils/` 目录**: **【工具箱】** 提供了专一、可复用的功能函数,如 `git_helper.py` 只负责克隆,`file_parser.py` 只负责解析文件,这让 `services` 层的代码更整洁。\n\n  * **`src/worker/tasks.py`**: **【后台工人】** 定义了耗时的后台任务(如 `process_repository_task`)。当需要处理一个大仓库时,API会把这个任务“扔”给它,然后立即返回,不阻塞主流程。\n\n  * **`tests/` 目录**: **【质量保证】** 存放所有的单元测试和集成测试,确保代码质量和功能正确性。","file_path":"architecture.md","start_line":181,"score":0.015873015873015872,"metadata":{"start_line":181,"language":"markdown","content":"* **`src/services/vector_store.py`**: **【向量数据库适配器】** 封装了所有与 ChromaDB 的直接交互,提供如“创建集合”、“添加文档”、“查询向量”等标准接口,使上层服务无需关心 ChromaDB 的具体实现细节。\n\n  * **`src/utils/` 目录**: **【工具箱】** 提供了专一、可复用的功能函数,如 `git_helper.py` 只负责克隆,`file_parser.py` 只负责解析文件,这让 `services` 层的代码更整洁。\n\n  * **`src/worker/tasks.py`**: **【后台工人】** 定义了耗时的后台任务(如 `process_repository_task`)。当需要处理一个大仓库时,API会把这个任务“扔”给它,然后立即返回,不阻塞主流程。\n\n  * **`tests/` 目录**: **【质量保证】** 存放所有的单元测试和集成测试,确保代码质量和功能正确性。","source":"architecture.md","file_path":"architecture.md","file_type":"document","chunk_index":30}},{"id":"chunk_4adb1c93-7e80-4a58-904c-d637ab0bb220_238","content":"文件路径: src/schemas/repository.py\n\n\"\"\"\n仓库分析相关的 Pydantic 模式定义\n定义 API 请求和响应的数据结构\n\"\"\"\n\nfrom pydantic import BaseModel\nfrom typing import Optional, Dict, Any, List\nfrom enum import Enum\n\nclass EmbeddingProvider(str, Enum):\n    \"\"\"Embedding 模型提供商枚举\"\"\"\n    OPENAI = \"openai\"\n    AZURE = \"azure\"\n    HUGGINGFACE = \"huggingface\"\n    OLLAMA = \"ollama\"\n    GOOGLE = \"google\"\n    QWEN = \"qwen\"\n\nclass LLMProvider(str, Enum):\n    \"\"\"LLM 模型提供商枚举\"\"\"\n    OPENAI = \"openai\"\n    AZURE = \"azure\"\n    HUGGINGFACE = \"huggingface\"\n    OLLAMA = \"ollama\"\n    DEEPSEEK = \"deepseek\"\n    GOOGLE = \"google\"\n    QWEN = \"qwen\"\n\nclass GenerationMode(str, Enum):\n    \"\"\"生成模式枚举\"\"\"\n    SERVICE = \"service\"  # 在服务端生成答案\n    PLUGIN = \"plugin\"    # 只返回上下文,由插件生成答案\n\nclass TaskStatus(str, Enum):\n    \"\"\"任务状态枚举\"\"\"\n    PENDING = \"pending\"\n    PROCESSING = \"processing\"\n    SUCCESS = \"success\"\n    FAILED = \"failed\"\n    CANCELLED = \"cancelled\"","file_path":"src/schemas/repository.py","start_line":1,"score":0.015625,"metadata":{"source":"src/schemas/repository.py","start_line":1,"file_type":"code","content":"文件路径: src/schemas/repository.py\n\n\"\"\"\n仓库分析相关的 Pydantic 模式定义\n定义 API 请求和响应的数据结构\n\"\"\"\n\nfrom pydantic import BaseModel\nfrom typing import Optional, Dict, Any, List\nfrom enum import Enum\n\nclass EmbeddingProvider(str, Enum):\n    \"\"\"Embedding 模型提供商枚举\"\"\"\n    OPENAI = \"openai\"\n    AZURE = \"azure\"\n    HUGGINGFACE = \"huggingface\"\n    OLLAMA = \"ollama\"\n    GOOGLE = \"google\"\n    QWEN = \"qwen\"\n\nclass LLMProvider(str, Enum):\n    \"\"\"LLM 模型提供商枚举\"\"\"\n    OPENAI = \"openai\"\n    AZURE = \"azure\"\n    HUGGINGFACE = \"huggingface\"\n    OLLAMA = \"ollama\"\n    DEEPSEEK = \"deepseek\"\n    GOOGLE = \"google\"\n    QWEN = \"qwen\"\n\nclass GenerationMode(str, Enum):\n    \"\"\"生成模式枚举\"\"\"\n    SERVICE = \"service\"  # 在服务端生成答案\n    PLUGIN = \"plugin\"    # 只返回上下文,由插件生成答案\n\nclass TaskStatus(str, Enum):\n    \"\"\"任务状态枚举\"\"\"\n    PENDING = \"pending\"\n    PROCESSING = \"processing\"\n    SUCCESS = \"success\"\n    FAILED = \"failed\"\n    CANCELLED = \"cancelled\"","file_path":"src/schemas/repository.py","chunk_index":238,"language":"python"}},{"id":"chunk_4adb1c93-7e80-4a58-904c-d637ab0bb220_44","content":"## 🚀 核心功能\n\n- **🤖 智能代码问答**: 基于检索增强生成(RAG)技术,提供精准的、上下文感知的代码解释和建议。\n- **⚡️ 全自动处理**: 只需提供一个 GitHub 仓库 URL,即可自动完成代码克隆、解析、分块、向量化和索引。\n- **🔌 高度可扩展**: 轻松更换或扩展 LLM、Embedding 模型和向量数据库,支持 OpenAI、Azure、Cohere、HuggingFace 等多种模型。\n- **🔍 混合搜索**: 结合了向量搜索和 BM25 关键字搜索,确保在不同类型的查询下都能获得最佳的上下文检索效果。\n- **⚙️ 异步任务处理**: 使用 Celery 和 Redis 处理耗时的仓库索引任务,确保 API 服务的响应速度和稳定性。\n- **🐳 一键部署**: 完整的 Docker-Compose 配置,一行命令即可启动所有服务(API、Worker、数据库等)。","file_path":"README_ZH.md","start_line":81,"score":0.015384615384615385,"metadata":{"file_path":"README_ZH.md","file_type":"document","content":"## 🚀 核心功能\n\n- **🤖 智能代码问答**: 基于检索增强生成(RAG)技术,提供精准的、上下文感知的代码解释和建议。\n- **⚡️ 全自动处理**: 只需提供一个 GitHub 仓库 URL,即可自动完成代码克隆、解析、分块、向量化和索引。\n- **🔌 高度可扩展**: 轻松更换或扩展 LLM、Embedding 模型和向量数据库,支持 OpenAI、Azure、Cohere、HuggingFace 等多种模型。\n- **🔍 混合搜索**: 结合了向量搜索和 BM25 关键字搜索,确保在不同类型的查询下都能获得最佳的上下文检索效果。\n- **⚙️ 异步任务处理**: 使用 Celery 和 Redis 处理耗时的仓库索引任务,确保 API 服务的响应速度和稳定性。\n- **🐳 一键部署**: 完整的 Docker-Compose 配置,一行命令即可启动所有服务(API、Worker、数据库等)。","source":"README_ZH.md","start_line":81,"language":"markdown","chunk_index":44}},{"id":"chunk_4adb1c93-7e80-4a58-904c-d637ab0bb220_307","content":"文件路径: src/api/v1/endpoints/repositories.py\n\nfrom fastapi import APIRouter, HTTPException, BackgroundTasks\nfrom ....schemas.repository import *\nimport uuid\nfrom ....services.task_queue import task_queue\nfrom ....worker.tasks import process_repository_task\nfrom ....db.session import get_db_session\nfrom ....db.models import AnalysisSession, TaskStatus\nfrom ....services.query_service import QueryService\nfrom datetime import datetime, timezone\nimport logging\n\nlogger = logging.getLogger(__name__)\n\nrouter = APIRouter(\n    prefix=\"/repos\",\n    tags=[\"repos\"],\n    responses={404: {\"description\": \"Not found\"}},\n)\n\n@router.post(\"/analyze\")\nasync def analyze(req: RepoAnalyzeRequest):\n    \"\"\"\n    分析仓库\n    接收包含 embedding_config 的请求,并将任务推送到 Celery 队列进行异步处理\n    \"\"\"\n    try:\n        logger.info(f\"🚀 [API请求] 收到仓库分析请求 - URL: {req.repo_url}\")\n        logger.info(f\"⚙️ [请求配置] Embedding提供商: {req.embedding_config.provider}, 模型: {req.embedding_config.model_name}\")","file_path":"src/api/v1/endpoints/repositories.py","start_line":1,"score":0.015151515151515152,"metadata":{"start_line":1,"source":"src/api/v1/endpoints/repositories.py","file_path":"src/api/v1/endpoints/repositories.py","content":"文件路径: src/api/v1/endpoints/repositories.py\n\nfrom fastapi import APIRouter, HTTPException, BackgroundTasks\nfrom ....schemas.repository import *\nimport uuid\nfrom ....services.task_queue import task_queue\nfrom ....worker.tasks import process_repository_task\nfrom ....db.session import get_db_session\nfrom ....db.models import AnalysisSession, TaskStatus\nfrom ....services.query_service import QueryService\nfrom datetime import datetime, timezone\nimport logging\n\nlogger = logging.getLogger(__name__)\n\nrouter = APIRouter(\n    prefix=\"/repos\",\n    tags=[\"repos\"],\n    responses={404: {\"description\": \"Not found\"}},\n)\n\n@router.post(\"/analyze\")\nasync def analyze(req: RepoAnalyzeRequest):\n    \"\"\"\n    分析仓库\n    接收包含 embedding_config 的请求,并将任务推送到 Celery 队列进行异步处理\n    \"\"\"\n    try:\n        logger.info(f\"🚀 [API请求] 收到仓库分析请求 - URL: {req.repo_url}\")\n        logger.info(f\"⚙️ [请求配置] Embedding提供商: {req.embedding_config.provider}, 模型: {req.embedding_config.model_name}\")","chunk_index":307,"file_type":"code","language":"python"}},{"id":"chunk_4adb1c93-7e80-4a58-904c-d637ab0bb220_88","content":"if success:\n            logger.info(f\"✅ [任务完成] 会话ID: {session_id} - 仓库分析成功完成\")\n            return {\n                \"success\": True,\n                \"session_id\": session_id,\n                \"message\": \"Repository analysis completed successfully\"\n            }\n        else:\n            logger.error(f\"❌ [任务失败] 会话ID: {session_id} - 仓库分析处理失败\")\n            return {\n                \"success\": False,\n                \"session_id\": session_id,\n                \"error\": \"Repository analysis failed\"\n            }\n\n    except Exception as e:\n        logger.error(f\"💥 [任务异常] 会话ID: {session_id}, 错误详情: {str(e)}\")\n        return {\n            \"success\": False,\n            \"session_id\": session_id,\n            \"error\": str(e)\n        }\n\n@celery_app.task(bind=True, name=\"process_query\")","file_path":"src/worker/tasks.py","start_line":41,"score":0.014925373134328358,"metadata":{"chunk_index":88,"file_path":"src/worker/tasks.py","language":"python","content":"if success:\n            logger.info(f\"✅ [任务完成] 会话ID: {session_id} - 仓库分析成功完成\")\n            return {\n                \"success\": True,\n                \"session_id\": session_id,\n                \"message\": \"Repository analysis completed successfully\"\n            }\n        else:\n            logger.error(f\"❌ [任务失败] 会话ID: {session_id} - 仓库分析处理失败\")\n            return {\n                \"success\": False,\n                \"session_id\": session_id,\n                \"error\": \"Repository analysis failed\"\n            }\n\n    except Exception as e:\n        logger.error(f\"💥 [任务异常] 会话ID: {session_id}, 错误详情: {str(e)}\")\n        return {\n            \"success\": False,\n            \"session_id\": session_id,\n            \"error\": str(e)\n        }\n\n@celery_app.task(bind=True, name=\"process_query\")","file_type":"code","source":"src/worker/tasks.py","start_line":41}},{"id":"chunk_4adb1c93-7e80-4a58-904c-d637ab0bb220_43","content":"---\n**请注意,目前项目仍在开发中,还无法正常使用**\n\n**GithubBot** 是一个功能强大的 AI 框架,旨在彻底改变开发者与代码库的交互方式。它能够自动“学习”一个 GitHub 仓库的全部代码和文档,并通过一个智能聊天机器人,用自然语言回答关于该仓库的任何问题——从“这个函数是做什么的?”到“如何实现一个新功能?”。","file_path":"README_ZH.md","start_line":61,"score":0.014705882352941176,"metadata":{"source":"README_ZH.md","language":"markdown","file_path":"README_ZH.md","file_type":"document","content":"---\n**请注意,目前项目仍在开发中,还无法正常使用**\n\n**GithubBot** 是一个功能强大的 AI 框架,旨在彻底改变开发者与代码库的交互方式。它能够自动“学习”一个 GitHub 仓库的全部代码和文档,并通过一个智能聊天机器人,用自然语言回答关于该仓库的任何问题——从“这个函数是做什么的?”到“如何实现一个新功能?”。","start_line":61,"chunk_index":43}},{"id":"chunk_4adb1c93-7e80-4a58-904c-d637ab0bb220_292","content":"def get_repository_list() -> list:\n    \"\"\"\n    获取所有已克隆的仓库列表\n\n    Returns:\n        list: 仓库目录列表\n    \"\"\"\n    repos_base_dir = settings.GIT_CLONE_DIR\n    if not os.path.exists(repos_base_dir):\n        return []\n\n    repositories = []\n    for item in os.listdir(repos_base_dir):\n        repo_path = os.path.join(repos_base_dir, item)\n        if os.path.isdir(repo_path):\n            try:\n                # 验证是否为有效的 Git 仓库\n                git.Repo(repo_path)\n                repositories.append({\n                    \"name\": item,\n                    \"path\": repo_path\n                })\n            except InvalidGitRepositoryError:\n                logger.warning(f\"发现无效的 Git 仓库目录: {repo_path}\")\n                continue\n\n    return repositories","file_path":"src/utils/git_helper.py","start_line":261,"score":0.014492753623188406,"metadata":{"file_path":"src/utils/git_helper.py","start_line":261,"chunk_index":292,"content":"def get_repository_list() -> list:\n    \"\"\"\n    获取所有已克隆的仓库列表\n\n    Returns:\n        list: 仓库目录列表\n    \"\"\"\n    repos_base_dir = settings.GIT_CLONE_DIR\n    if not os.path.exists(repos_base_dir):\n        return []\n\n    repositories = []\n    for item in os.listdir(repos_base_dir):\n        repo_path = os.path.join(repos_base_dir, item)\n        if os.path.isdir(repo_path):\n            try:\n                # 验证是否为有效的 Git 仓库\n                git.Repo(repo_path)\n                repositories.append({\n                    \"name\": item,\n                    \"path\": repo_path\n                })\n            except InvalidGitRepositoryError:\n                logger.warning(f\"发现无效的 Git 仓库目录: {repo_path}\")\n                continue\n\n    return repositories","language":"python","file_type":"code","source":"src/utils/git_helper.py"}},{"id":"chunk_4adb1c93-7e80-4a58-904c-d637ab0bb220_95","content":"logger.info(f\"📋 [仓库信息] 会话ID: {session_id} - 解析仓库信息\")\n                owner, repo_name = self.git_helper.extract_repo_info(repo_url)\n                self._update_session_repo_info(db, session_id, repo_name, owner)\n                logger.info(f\"📝 [仓库详情] 会话ID: {session_id} - 仓库: {owner}/{repo_name}\")\n                self._update_task_progress(task_instance, 35, \"仓库信息解析完成\")\n            except Exception as e:\n                logger.error(f\"❌ [关键失败] 会话ID: {session_id} - 仓库克隆或信息解析失败: {e}\")\n                raise # 这是关键步骤,失败则无法继续","file_path":"src/services/ingestion_service.py","start_line":81,"score":0.014285714285714285,"metadata":{"chunk_index":95,"file_path":"src/services/ingestion_service.py","start_line":81,"file_type":"code","source":"src/services/ingestion_service.py","language":"python","content":"logger.info(f\"📋 [仓库信息] 会话ID: {session_id} - 解析仓库信息\")\n                owner, repo_name = self.git_helper.extract_repo_info(repo_url)\n                self._update_session_repo_info(db, session_id, repo_name, owner)\n                logger.info(f\"📝 [仓库详情] 会话ID: {session_id} - 仓库: {owner}/{repo_name}\")\n                self._update_task_progress(task_instance, 35, \"仓库信息解析完成\")\n            except Exception as e:\n                logger.error(f\"❌ [关键失败] 会话ID: {session_id} - 仓库克隆或信息解析失败: {e}\")\n                raise # 这是关键步骤,失败则无法继续"}}
    ],
  "generation_mode":"service",
  "generation_time":49892,
  "retrieval_time":671,
  "total_time":50568
}
```

#### 获取任务详细信息

- GET /api/v1/repos/query/info/{session_id}
- 功能 : 获取查询任务的综合信息
- GithubBot的响应例子:
```json
{
  "session_id":"51a9871d-8d55-4077-b2c1-cf1893b79183",
  "status":"SUCCESS",
  "ready":true,
  "successful":true,
  "execution_info":{
    "has_result":true,
    "result_type":"dict",
    "error":null,
    "traceback":null
  },
  "result_summary":{
    "success":true,
    "has_answer":true,
    "context_chunks":10,
    "generation_mode":"service",
    "timing":{
      "retrieval_time":671,
      "generation_time":49892,
      "total_time":50568
    }
  }
}
```

#### 4.4 清除BM25缓存
- **API路径**: `POST /api/v1/repos/cache/clear`
- **功能**: 清除BM25缓存以应用改进的分词和文件名匹配逻辑
- **适用场景**: 系统更新分词算法、缓存数据过时、调试搜索功能问题时
- GithubBot响应示例:

```json
{
  "status": "success",
  "message": "BM25 cache cleared successfully"
}
```

### 4.5 健康检查
- **API路径**: `GET /health`
- **功能**: 检查 GithubBot 服务及其依赖组件的健康状态
- **适用场景**: 服务监控、负载均衡器健康检查、运维状态验证
- **检查组件**:
  - 数据库连接 (PostgreSQL)
  - Redis 连接 (通过 Celery)
  - ChromaDB 连接 (向量数据库)
- **响应示例**:
```json
{
  "status": "healthy",
  "service": "github-bot",
  "version": "1.0.0",
  "timestamp": "2024-01-01T12:00:00.000000",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "chromadb": "healthy"
  }
}
```
- **状态说明**:
  - `healthy`: 所有组件正常
  - `degraded`: 部分非关键组件异常
  - `unhealthy`: 关键组件异常

## 5. 会话持久化

插件的内存是临时的，重启会导致所有信息丢失。因此，必须将用户的状态和 `session_id` 持久化。

-   **方案**: 使用轻量级的数据库，如 **SQLite**。
-   **数据表 `user_sessions` 设计**:
    -   `user_id` (TEXT, PRIMARY KEY): 微信用户的唯一标识。
    -   `state` (TEXT): 用户当前状态，如 `waiting_for_repo`。
    -   `github_bot_session_id` (TEXT, NULLABLE): 关联的 `GithubBot` **分析**会话ID。
    -   `repo_url` (TEXT, NULLABLE): 当前正在分析或问答的仓库URL。
    -   `updated_at` (TIMESTAMP): 最后更新时间。

## 6. 错误处理与用户反馈

明确的错误反馈是良好用户体验的关键。

| 错误场景                 | 插件内部操作                    | 给用户的反馈                                                               |
| :----------------------- | :-------------------------- | :------------------------------------------------------------------------- |
| `GithubBot` 服务不在线     | `GithubBotClient` 请求失败  | “抱歉，仓库分析服务当前不可用，请稍后再试。”                               |
| 用户发送的不是有效URL       | `MessageHandler` 校验失败   | “您发送的似乎不是一个有效的 GitHub 仓库链接，请检查后重试。”               |
| `GithubBot` 分析失败      | `/status` 接口返回 `failed` | “抱歉，仓库 `owner/repo` 分析失败。可能是仓库过大或包含不支持的文件类型。” |
| 查询时 `session_id` 失效   | `/query` 接口返回 404       | “抱歉，当前的问答会话已失效，请重新使用 `/repo` 指令开始一个新的分析。”    |

## 7. 数据模型设计

### 7.1 用户会话模型
这是整个插件的核心数据模型，**合并了状态和会话管理**，存储在持久化数据库（如SQLite）中。
```python
@dataclass
class UserSession:
    user_id: str  # 微信用户唯一ID (主键)
    state: str  # 用户当前状态, e.g., 'idle', 'waiting_for_repo', 'analyzing', 'ready_for_query', 'waiting_for_answer'
    repo_url: Optional[str]  # 当前正在处理的仓库URL
    analysis_session_id: Optional[str]  # GithubBot返回的【分析】会话ID
    query_session_id: Optional[str] # GithubBot返回的【查询】会话ID
    question: Optional[str] # 用户当前提问的问题内容
    last_activity_at: datetime # 用户最后活跃时间，用于清理僵尸会话
```

### 7.2 配置模型
通过YAML文件进行管理，使配置与代码分离。
```python
@dataclass
class PluginConfig:
    githubbot_api_base: str # GithubBot API 的根地址
    githubbot_api_key: Optional[str] # (推荐) 用于认证的API Key
    api_timeout: int # API 请求超时时间（秒）
    session_cleanup_interval: int # 定期清理不活跃用户状态的间隔（秒）
    session_ttl: int # 用户状态的存活时间（秒），超过此时间未活动则被清理
    # 默认的 Embedding 和 LLM 配置
    default_embedding_config: dict
    default_llm_config: dict
```

## 8. 核心模块实现

### 8.1 插件主类结构
结构保持简洁，核心逻辑委托给其他组件。

```python
class RepoInsightPlugin(BasePlugin):
    def __init__(self, host: APIHost):
        # 加载配置
        self.config = ConfigManager("config.yaml").get_config()
        # 初始化数据库和状态管理器
        self.state_manager = StateManager("user_states.db")
        # 初始化API客户端
        self.api_client = GithubBotClient(
            base_url=self.config.githubbot_api_base,
            api_key=self.config.githubbot_api_key,
            timeout=self.config.api_timeout
        )
        # 初始化后台任务调度器
        self.scheduler = TaskScheduler(self.state_manager, self.api_client)
        # 初始化消息处理器
        self.message_handler = MessageHandler(self.state_manager, self.api_client, self.scheduler)
    
    async def initialize(self):
        # 启动后台任务：如定期轮询分析状态、清理不活跃用户
        await self.scheduler.start()
        logger.info("RepoInsight 插件已启动并初始化完成。")
    
    @handler(PersonNormalMessageReceived)
    async def handle_person_message(self, ctx: EventContext):
        # 将消息转发给 MessageHandler 处理
        user_id = ctx.event.sender.id
        message_text = ctx.event.message.get_plaintext()
        reply_text = await self.message_handler.handle(user_id, message_text)
        if reply_text:
            await ctx.send(reply_text)
    
    @handler(GroupNormalMessageReceived)
    async def handle_group_message(self, ctx: EventContext):
        # 检查消息是否@了机器人
        if not ctx.event.is_mentioned:
            return

        # 将消息转发给 MessageHandler 处理
        # 注意：群聊中，状态管理仍应基于单个用户的ID
        user_id = ctx.event.sender.id
        # 移除@信息，获取纯文本
        message_text = ctx.event.message.get_plaintext(exclude_at=True).strip()
        
        reply_text = await self.message_handler.handle(user_id, message_text)
        if reply_text:
            # 在群里回复消息
            await ctx.send(reply_text)
```

### 8.2 状态管理器 (`StateManager`)
负责所有用户状态的持久化读写。
```python
```python
class StateManager:
    def __init__(self, db_path: str):
        # 初始化数据库连接 (e.g., SQLite)
        self.db = self._init_db(db_path)

    def get_user_state(self, user_id: str) -> Optional[UserState]:
        # 从数据库获取用户状态
        pass

    def update_user_state(self, user_id: str, new_state_data: dict):
        # 创建或更新用户状态
        # 例如: update_user_state(user_id, {'state': 'analyzing', 'analysis_session_id': 'xyz'})
        pass

    def clear_user_state(self, user_id: str):
        # 清理用户状态，使其回到 idle
        pass

    def get_users_in_state(self, state: str) -> List[UserState]:
        # 获取所有处于特定状态的用户列表 (例如，获取所有 'analyzing' 的用户以进行轮询)
        pass
    
    def get_all_active_users(self) -> List[UserState]:
        # 获取所有非 idle 状态的用户
        pass
```

### 8.3 API客户端
严格按照 `GithubBot` 真实接口进行封装。
```python
class GithubBotClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 30):
        # ... 初始化 aiohttp.ClientSession 和请求头

    async def start_analysis(self, repo_url: str, config: dict) -> dict:
        # 调用 POST /api/v1/repos/analyze
        pass

    async def get_analysis_status(self, session_id: str) -> dict:
        # 调用 GET /api/v1/repos/status/{session_id}
        pass

    async def submit_query(self, analysis_session_id: str, question: str, config: dict) -> dict:
        # 调用 POST /api/v1/repos/query
        pass

    async def get_query_result(self, query_session_id: str) -> dict:
        # 调用 GET /api/v1/repos/query/result/{query_session_id}
        pass

    async def check_health(self) -> bool:
        # 调用 GET /health
        pass
```

## 9. 消息处理流程

### 9.1 消息处理流程 (`MessageHandler`)
根据用户当前状态（从 `StateManager` 获取）决定如何处理消息。
```python
class MessageHandler:
    def __init__(self, state_manager: StateManager, api_client: GithubBotClient, scheduler: TaskScheduler, config: PluginConfig):
        self.state_manager = state_manager
        self.api_client = api_client
        self.scheduler = scheduler
        self.config = config

    async def handle(self, user_id: str, text: str) -> str:
        # 1. 获取或创建用户状态
        user_state = self.state_manager.get_user_state(user_id)
        if not user_state:
            self.state_manager.update_user_state(user_id, {'state': 'idle'})
            user_state = self.state_manager.get_user_state(user_id)
        
        # 2. 检查是否为指令
        if text.strip().startswith('/'):
            return await self.handle_command(user_state, text.strip())

        # 3. 根据状态进行分发
        state = user_state.state
        if state == 'waiting_for_repo':
            return await self.handle_repo_url(user_state, text)
        elif state == 'analyzing':
            return "仓库正在分析中，请耐心等待分析完成的通知。您也可以使用 /status 查看进度。"
        elif state == 'ready_for_query':
            return await self.handle_question(user_state, text)
        elif state == 'waiting_for_answer':
            return f"您的问题正在处理中，请耐心等待答案。当前问题：\"{user_state.question or '未知'}\"\n答案准备好后会立即通知您。"
        else: # idle
            return "您好！请使用 /repo 指令进入仓库问答模式。使用 /help 查看所有指令。"

    async def handle_command(self, user_state: UserState, text: str) -> str:
        command = text.split(' ')[0]
        user_id = user_state.user_id

        if command == '/repo':
            self.state_manager.update_user_state(user_id, {'state': 'waiting_for_repo'})
            return "您好！已进入仓库分析模式。请直接发送一个 GitHub 仓库的 URL。随时可以通过 /exit 退出。"
        
        elif command == '/exit':
            self.state_manager.clear_user_state(user_id)
            return "已退出仓库分析模式，感谢您的使用！"
            
        elif command == '/status':
            if user_state.state == 'analyzing':
                try:
                    status_data = await self.api_client.get_analysis_status(user_state.analysis_session_id)
                    progress = status_data.get('progress', 0) * 100
                    details = status_data.get('details', '正在处理...')
                    return f"分析进度: {progress:.2f}%\n状态: {details}"
                except Exception as e:
                    logger.error(f"获取状态失败: {e}")
                    return "获取分析状态失败，请稍后再试。"
            elif user_state.state == 'ready_for_query':
                return f"仓库 {user_state.repo_url} 已分析完成，可以直接提问。"
            elif user_state.state == 'waiting_for_answer':
                return f"正在处理您的问题：\"{user_state.question or '未知'}\"\n答案准备好后会立即通知您。"
            else:
                return "当前没有正在进行的分析或查询任务。"

        elif command == '/help':
            return """
RepoInsight 插件帮助:
/repo - 进入仓库分析模式
/exit - 退出仓库分析模式
/status - 查看当前分析任务的状态
/help - 显示本帮助信息
"""
        else:
            return "无法识别的指令。请使用 /help 查看可用指令。"

    async def handle_repo_url(self, user_state: UserState, text: str) -> str:
        repo_url = text.strip()
        # 使用正则表达式验证GitHub仓库URL
        github_repo_pattern = re.compile(r'^(?:https?:\/\/)?(?:www\.)?github\.com\/([a-zA-Z0-9-]{1,39})\/([a-zA-Z0-9-_\.]{1,100})(?:\.git)?\/?$')
        match = github_repo_pattern.match(repo_url)

        if not match:
            return "您发送的似乎不是一个有效的 GitHub 仓库链接，请检查后重试。链接应形如 `https://github.com/owner/repo`。"
        
        try:
            # 调用API开始分析
            response = await self.api_client.start_analysis(repo_url, self.config.default_embedding_config)
            analysis_session_id = response.get("session_id")

            if not analysis_session_id:
                raise ValueError("API响应中缺少session_id")

            # 更新用户状态
            self.state_manager.update_user_state(user_state.user_id, {
                'state': 'analyzing',
                'repo_url': repo_url,
                'analysis_session_id': analysis_session_id
            })
            return "✅ 已收到仓库链接，正在请求分析，请稍候... 这可能需要几分钟时间。分析完成后会通知您。"
        except Exception as e:
            logger.error(f"请求分析失败: {e}")
            return f"请求分析失败，请检查URL或联系管理员。错误: {e}"

    async def handle_question(self, user_state: UserState, text: str) -> str:
        question = text.strip()
        analysis_session_id = user_state.analysis_session_id

        if not analysis_session_id:
            return "错误：找不到有效的分析会话，请使用 /repo 重新开始。"

        try:
            # 异步处理问答 - 改进版本：避免阻塞式轮询
            # 1. 提交问题
            submit_response = await self.api_client.submit_query(
                analysis_session_id, question, self.config.default_llm_config
            )
            query_session_id = submit_response.get("session_id")
            if not query_session_id:
                raise ValueError("提交问题的API响应中缺少session_id")
            
            # 2. 更新用户状态为等待查询结果，并记录查询会话ID
            self.state_manager.update_user_state(user_state.user_id, {
                'state': 'waiting_for_answer',
                'query_session_id': query_session_id,
                'question': question
            })
            
            # 3. 将查询任务交给后台调度器处理，立即返回确认消息
            await self.scheduler.schedule_query_polling(user_state.user_id, query_session_id)
            
            return f"✅ 已收到您的问题：\"{question}\"\n正在为您查找答案，请稍候... 答案准备好后会立即通知您。"
            
        except Exception as e:
            logger.error(f"处理问题时出错: {e}")
            return f"处理您的问题时发生错误，请稍后再试。错误: {e}"
```

### 9.2 异步任务处理 (`TaskScheduler`)
使用 `apscheduler` 等库实现，与主消息流程解耦。

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

class TaskScheduler:
    def __init__(self, state_manager: StateManager, api_client: GithubBotClient, host: APIHost, config: PluginConfig):
        self.state_manager = state_manager
        self.api_client = api_client
        self.host = host # 用于主动发送消息
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self.query_tasks = {}  # 存储查询任务的映射 {user_id: task_info}

    async def start(self):
        # 添加定时任务
        self.scheduler.add_job(self.poll_analysis_status, 'interval', seconds=30, id="poll_analysis_job")
        self.scheduler.add_job(self.poll_query_results, 'interval', seconds=10, id="poll_query_job")
        self.scheduler.add_job(self.cleanup_inactive_users, 'interval', minutes=self.config.session_cleanup_interval, id="cleanup_job")
        self.scheduler.start()
        logger.info("后台任务调度器已启动。")

    async def schedule_query_polling(self, user_id: str, query_session_id: str):
        """安排查询结果轮询任务"""
        self.query_tasks[user_id] = {
            'query_session_id': query_session_id,
            'start_time': datetime.now(),
            'retry_count': 0
        }
        logger.info(f"已为用户 {user_id} 安排查询轮询任务，会话ID: {query_session_id}")

    async def poll_analysis_status(self):
        analyzing_users = self.state_manager.get_users_in_state('analyzing')
        for user_state in analyzing_users:
            try:
                status_data = await self.api_client.get_analysis_status(user_state.analysis_session_id)
                if status_data.get('status') == 'success':
                    logger.info(f"用户 {user_state.user_id} 的仓库 {user_state.repo_url} 分析完成。")
                    # 更新状态
                    self.state_manager.update_user_state(user_state.user_id, {'state': 'ready_for_query'})
                    # 主动发送通知
                    notification = f"🎉 好消息！您的仓库 {user_state.repo_url} 已分析完成。现在可以开始提问了！"
                    await self.host.send_person_message(user_state.user_id, notification)
                elif status_data.get('status') == 'failed':
                    logger.error(f"用户 {user_state.user_id} 的仓库 {user_state.repo_url} 分析失败。")
                    self.state_manager.clear_user_state(user_state.user_id)
                    # 主动发送失败通知
                    error_msg = status_data.get('error_message', '未知错误')
                    notification = f"😥 抱歉，您的仓库 {user_state.repo_url} 分析失败: {error_msg}"
                    await self.host.send_person_message(user_state.user_id, notification)
            except Exception as e:
                logger.error(f"轮询用户 {user_state.user_id} 状态时发生错误: {e}")

    async def poll_query_results(self):
        """轮询查询结果 - 非阻塞式后台处理"""
        current_time = datetime.now()
        completed_users = []
        
        for user_id, task_info in self.query_tasks.items():
            try:
                query_session_id = task_info['query_session_id']
                start_time = task_info['start_time']
                retry_count = task_info['retry_count']
                
                # 检查是否超时 (最多等待5分钟)
                if (current_time - start_time).total_seconds() > 300:
                    logger.warning(f"用户 {user_id} 的查询任务超时")
                    await self.host.send_person_message(user_id, "⏰ 查询处理超时，请稍后重试或尝试简化您的问题。")
                    self.state_manager.update_user_state(user_id, {'state': 'ready_for_query'})
                    completed_users.append(user_id)
                    continue
                
                # 获取查询结果
                result_response = await self.api_client.get_query_result(query_session_id)
                status = result_response.get('status')
                
                if status == 'success':
                    # 查询成功，发送答案
                    answer = result_response.get('answer', '未能获取到答案。')
                    user_state = self.state_manager.get_user_state(user_id)
                    question = user_state.question if user_state else '您的问题'
                    
                    response_msg = f"💡 关于问题：\"{question}\"\n\n{answer}"
                    await self.host.send_person_message(user_id, response_msg)
                    
                    # 更新状态回到可查询状态
                    self.state_manager.update_user_state(user_id, {
                        'state': 'ready_for_query',
                        'query_session_id': None,
                        'question': None
                    })
                    completed_users.append(user_id)
                    logger.info(f"用户 {user_id} 的查询已完成并发送答案")
                    
                elif status == 'failed':
                    # 查询失败
                    error_msg = result_response.get('error_message', '未知错误')
                    await self.host.send_person_message(user_id, f"❌ 查询处理失败: {error_msg}\n请稍后重试。")
                    
                    self.state_manager.update_user_state(user_id, {
                        'state': 'ready_for_query',
                        'query_session_id': None,
                        'question': None
                    })
                    completed_users.append(user_id)
                    logger.error(f"用户 {user_id} 的查询失败: {error_msg}")
                    
                elif status == 'processing':
                    # 仍在处理中，增加重试计数
                    task_info['retry_count'] = retry_count + 1
                    if retry_count > 0 and retry_count % 30 == 0:  # 每5分钟发送一次进度提醒
                        await self.host.send_person_message(user_id, "🔄 您的问题仍在处理中，请耐心等待...")
                        
            except Exception as e:
                logger.error(f"轮询用户 {user_id} 查询结果时发生错误: {e}")
                # 发生错误时也清理任务
                await self.host.send_person_message(user_id, "❌ 查询处理时发生错误，请稍后重试。")
                self.state_manager.update_user_state(user_id, {
                    'state': 'ready_for_query',
                    'query_session_id': None,
                    'question': None
                })
                completed_users.append(user_id)
        
        # 清理已完成的任务
        for user_id in completed_users:
            self.query_tasks.pop(user_id, None)

    async def cleanup_inactive_users(self):
        logger.info("开始清理不活跃的用户状态...")
        all_users = self.state_manager.get_all_active_users()
        now = datetime.now()
        cleaned_count = 0
        for user_state in all_users:
            if now - user_state.last_activity_at > timedelta(seconds=self.config.session_ttl):
                self.state_manager.clear_user_state(user_state.user_id)
                logger.info(f"已清理不活跃用户 {user_state.user_id} 的状态。")
                cleaned_count += 1
        logger.info(f"不活跃用户状态清理完成，共清理 {cleaned_count} 个。")
```

## 10. 异步处理机制优化

### 10.1 轮询机制改进
原始的同步轮询机制存在以下问题：
- **阻塞性**：在等待查询结果时会阻塞整个消息处理流程
- **资源浪费**：每秒轮询一次，消耗大量CPU和网络资源
- **用户体验差**：用户在等待期间无法进行其他操作
- **并发限制**：无法同时处理多个用户的查询请求

**改进后的异步处理机制**：
1. **立即响应**：用户提交问题后立即收到确认消息，无需等待
2. **后台处理**：查询任务交给后台调度器处理，不阻塞主流程
3. **主动通知**：结果准备好后主动推送给用户
4. **并发支持**：可同时处理多个用户的查询请求
5. **资源优化**：降低轮询频率（10秒一次），减少资源消耗

### 10.2 状态管理增强
新增 `waiting_for_answer` 状态，完善用户交互流程：
- **状态流转**：`ready_for_query` → `waiting_for_answer` → `ready_for_query`
- **问题记录**：保存用户当前提问内容，便于状态查询和结果推送
- **超时处理**：5分钟超时机制，避免任务无限等待
- **错误恢复**：异常情况下自动恢复到可查询状态

## 11. 错误与异常处理
采用统一的异常处理策略，在 `GithubBotClient` 和 `MessageHandler` 中捕获异常，并返回对用户友好的提示。
- **API层面**: 在 `GithubBotClient` 的每个请求方法中使用 `try...except` 捕获 `aiohttp.ClientError`, `TimeoutError` 等，并向上抛出自定义异常，如 `APIConnectionError`。
- **业务层面**: 在 `MessageHandler` 中捕获 `APIConnectionError` 或其他业务逻辑异常（如URL验证失败），并生成对应的用户提示语。
- **日志**: 在所有异常捕获点记录详细的错误日志，便于排查问题。

### 11.1 异常分类
1. **网络异常**：API请求超时、连接失败
2. **业务异常**：仓库URL无效、分析失败
3. **系统异常**：内存不足、文件读写失败
4. **用户异常**：输入格式错误、权限不足


## 12. 配置管理

### 12.1 配置文件结构
配置文件结构应扁平化，直接对应 `PluginConfig` 数据模型，更易于管理和解析。
```yaml
# config.yaml

# GithubBot API 相关配置
githubbot_api_base: "http://localhost:8000"
githubbot_api_key: "your-secret-api-key" # 推荐填写，用于安全认证
api_timeout: 30 # API请求超时时间（秒）

# 用户会话/状态管理
session_cleanup_interval: 60 # 清理不活跃用户状态的间隔（分钟）
session_ttl: 3600 # 用户状态存活时间（秒），1小时无活动则被清理

# 默认的 Embedding 模型配置
# 这部分将作为请求体直接发送给 GithubBot
default_embedding_config:
  provider: "openai"
  model_name: "text-embedding-ada-002"
  api_key: "your-openai-api-key" # 注意：此key是给GithubBot使用的

# 默认的 LLM 模型配置
# 这部分将作为请求体直接发送给 GithubBot
default_llm_config:
  provider: "openai"
  model_name: "gpt-3.5-turbo"
  api_key: "your-openai-api-key" # 注意：此key是给GithubBot使用的
  temperature: 0.7

# 日志配置
logging:
  level: "INFO"
  file: "repo_insight_plugin.log"

```

### 12.2 配置加载
提供一个健壮的配置加载器，能处理文件不存在、格式错误等情况，并能方便地将加载的字典转换为 `PluginConfig` 对象。
```python
import yaml
from typing import Optional

class ConfigManager:
    def __init__(self, config_path: str = "config.yaml"):
        self.path = config_path
        self._config_data = self._load_from_file()

    def _load_from_file(self) -> dict:
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"配置文件 {self.path} 未找到，请根据文档创建。")
            raise
        except yaml.YAMLError as e:
            logger.error(f"配置文件 {self.path} 格式错误: {e}")
            raise

    def get_config(self) -> PluginConfig:
        """将加载的字典数据转换为 PluginConfig 类型提示对象"""
        try:
            # 这里可以添加更复杂的验证逻辑，例如使用 Pydantic
            return PluginConfig(**self._config_data)
        except TypeError as e:
            logger.error(f"配置文件内容与 PluginConfig 模型不匹配: {e}")
            raise
```

## 13. 测试策略
测试策略需要与新的模块设计对齐。
### 13.1 单元测试
- **StateManager**: 模拟数据库操作，测试 `get`, `update`, `clear` 等方法的逻辑是否正确。
- **ConfigManager**: 测试在配置文件存在、缺失、格式错误等情况下的行为。
- **MessageHandler**: 重点测试指令解析和基于不同 `state` 的逻辑分发是否正确，无需真实API调用（使用Mock）。
- **GithubBotClient**: 使用 `aiohttp.pytest_plugin` 等工具模拟API服务器，测试客户端能否正确发送请求和解析响应。

### 13.2 集成测试
- **插件与 `GithubBot` 服务**: 启动一个真实的 `GithubBot` 服务实例，测试插件能否成功完成一次完整的“分析->提问”流程。
- **插件与数据库**: 测试 `StateManager` 与真实SQLite数据库的交互，验证数据持久化和读取的正确性。
- **插件与 `LangBot` 核心**: 在一个最小化的 `LangBot` 环境中加载插件，测试事件处理器（`@handler`）是否能被正确触发。

### 13.3 端到端测试
- 模拟一个或多个微信用户，通过客户端发送消息，完整地测试从 `/repo` 指令到最终收到问答结果的全流程。
- 特别关注并发场景，例如多个用户同时请求分析。

## 14. 部署指南

### 14.1 环境要求
- Python 3.10+
- LangBot 4.0+
- GithubBot服务运行中
- 网络连接正常

### 14.2 安装步骤
1.  将插件文件夹放置于 LangBot 的 `plugins` 目录下。
2.  安装依赖: `pip install -r requirements.txt` (应包含 `pyyaml`, `apscheduler`, `aiohttp` 等)。
3.  **核心步骤**: 创建并正确填写 `config.yaml` 文件。确保 `githubbot_api_base` 指向您正在运行的 `GithubBot` 服务。
4.  重启 LangBot 服务。
5.  在 LangBot 的 WebUI 中检查插件是否加载成功，并查看启动日志。

### 14.3 配置检查
```bash
# 检查GithubBot服务状态
curl http://localhost:8000/api/v1/health

# 检查插件配置
python -c "from config import ConfigManager; print(ConfigManager()._config_data)"
```

## 15. 运维与监控
### 15.1 日志管理
- 记录所有API调用
- 记录用户操作轨迹
- 记录异常和错误信息

### 15.2 性能监控
- 监控API响应时间
- 监控内存使用情况
- 监控并发用户数

### 15.3 维护任务
- 定期清理过期会话
- 定期备份用户数据
- 定期更新依赖包