# RepoInsight 插件配置迁移指南

## 概述

RepoInsight 插件已成功迁移到 LangBot 的 WebUI 配置系统。用户现在可以直接在 LangBot 的 Web 界面中配置向量模型和语言模型，无需手动编辑配置文件。

## 配置项说明

### 向量模型配置

- **向量模型提供商** (`embedding_provider`): 选择向量模型提供商（OpenAI、Azure OpenAI、DeepSeek）
- **向量模型** (`embedding_model`): 指定使用的向量模型名称（如 text-embedding-3-small）
- **向量模型 API 密钥** (`embedding_api_key`): 向量模型服务的 API 密钥
- **向量模型基础 URL** (`embedding_base_url`): 自定义 API 基础 URL（可选）
- **最大令牌数** (`max_tokens`): 处理文本的最大令牌数限制
- **文本块大小** (`chunk_size`): 文档分块的大小
- **文本块重叠** (`chunk_overlap`): 相邻文本块之间的重叠大小

### 语言模型配置

- **语言模型提供商** (`llm_provider`): 选择语言模型提供商（OpenAI、Azure OpenAI、DeepSeek）
- **语言模型** (`llm_model`): 指定使用的语言模型名称（如 gpt-4o-mini）
- **语言模型 API 密钥** (`llm_api_key`): 语言模型服务的 API 密钥
- **语言模型基础 URL** (`llm_base_url`): 自定义 API 基础 URL（可选）

### 系统配置

- **生成模式** (`generation_mode`): 选择答案生成方式
  - `service`: 使用 GithubBot 后端服务生成答案
  - `plugin`: 使用 LangBot 的语言模型生成答案
- **GithubBot 基础 URL** (`githubbot_base_url`): GithubBot 服务的地址
- **数据库路径** (`database_path`): SQLite 数据库文件路径

### 功能开关

- **启用私聊功能** (`enable_private_chat`): 是否在私聊中响应用户
- **启用群聊功能** (`enable_group_chat`): 是否在群聊中响应用户
- **群聊中需要@机器人** (`require_mention_in_group`): 群聊中是否需要@机器人才响应

## 如何在 WebUI 中配置

1. 打开 LangBot 的 Web 管理界面
2. 导航到「插件管理」页面
3. 找到 RepoInsight 插件
4. 点击「配置」按钮
5. 填写相应的配置项
6. 点击「保存」应用配置

## 迁移完成的功能

✅ **已完成的迁移**:
- 移除了对 `config.yaml` 文件的依赖
- 所有配置项现在通过 WebUI 管理
- 插件能够实时接收配置更新
- 向量模型和语言模型配置完全可定制
- 功能开关可通过 WebUI 控制

✅ **配置验证**:
- 所有配置项都有合理的默认值
- 必填项已正确标记
- 配置类型验证已实现

## 注意事项

1. **API 密钥安全**: 请确保 API 密钥的安全性，不要在公共场所暴露
2. **服务地址**: 确保 GithubBot 服务正在运行并且地址配置正确
3. **模型兼容性**: 确认选择的模型与提供商兼容
4. **资源限制**: 根据实际需求调整令牌数和文本块大小

## 故障排除

如果遇到配置问题，请检查：

1. API 密钥是否正确
2. 网络连接是否正常
3. GithubBot 服务是否运行
4. 配置项是否填写完整
5. 查看 LangBot 日志获取详细错误信息