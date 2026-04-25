# Bad_Messages_In_WeChat_Groups

监控微信群聊中的可疑消息，通过关键词匹配 + LLM 大模型双重审核，确认恶意后 @提醒管理员并发送私信通知。

## 工作原理

```
[微信PC客户端] ← wxauto → [关键词匹配] → [LLM 审核] → [管理员通知]
                              ↓                    ↓              ↓
                        匹配关键词             判定"malicious"   群内@ + 私信
```

1. **关键词匹配** — 扫描群聊消息，匹配 `keywords.txt` 中配置的关键词
2. **LLM 审核** — 匹配到的消息发送给 OpenAI 兼容的大模型，判断是否为恶意消息（广告、诈骗、辱骂、代写代考等）
3. **管理员通知** — 确认恶意后，在群内一次性 @所有管理员，并逐个私信发送详细内容

## 功能特性

- 🕵️ **自动监控** — 后台线程轮询监控群聊，可配置轮询间隔
- 🧠 **LLM 审核** — 支持任何 OpenAI 兼容的 API（GPT、Claude、本地 ollama 等）
- 🔔 **管理员通知** — 群内 @提及 + 私信详细内容（支持微信号搜索）
- 🧹 **自动去重** — 基于内容哈希的智能去重，避免重复告警
- 🌐 **Web 管理界面** — 可视化配置群组、管理员、关键词、模型参数
- 📝 **关键词文件** — 支持直接编辑 `keywords.txt` 文件
- 💾 **零配置数据库** — 自动创建 SQLite 数据库，无需手动设置

## 系统要求

- Windows 10/11（需安装微信 PC 客户端）
- Python 3.10+
- [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170#latest-supported-redistributable-version)（最新版本）
- 微信 PC 客户端已登录，版本3.9.12.57

## 快速开始

### 1. 下载项目

```bash
git clone https://github.com/yourusername/Bad_Messages_In_WeChat_Groups.git
cd Bad_Messages_In_WeChat_Groups
```

### 2. 配置 start_master.bat

将项目根目录下的 `start_master.bat` **剪切**到项目文件夹的**父目录**中：

```
你的任意目录/
├── start_master.bat        ← 放在这里
└── Bad_Messages_In_WeChat_Groups/
    ├── app/
    ├── run.py
    ├── requirements.txt
    └── ...
```

### 3. 安装依赖

在项目目录中执行：

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

首次运行前，在项目目录中创建 `.env` 文件：

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-your-api-key-here
LLM_MODEL=gpt-4o-mini
```

> **支持任何 OpenAI 兼容 API**：DeepSeek、Claude（通过代理）、Azure OpenAI、Ollama 本地模型等。

### 5. 运行程序

双击 `start_master.bat`，或打开终端执行：

```bash
./start_master.bat
```

脚本会自动：
1. 从原始工程复制一份全新副本到 `_run/` 目录
2. 自动安装依赖
3. 启动 Web 服务器并打开浏览器
4. 访问 `http://127.0.0.1:8000` 进入管理界面

> ⚠️ **每次运行都会复制全新副本**，避免因旧数据导致的问题。

#### 持久化配置

如果需要长期保存设置（群组、管理员、关键词、LLM 参数等），可以直接在 `Bad_Messages_In_WeChat_Groups/` 文件夹中运行 `start.bat` 启动服务，并在 Web UI 中进行配置。这样下次使用 `start_master.bat` 时，复制出去的就是已经配置好的工程。数据库文件 `wechat_bot.db` 会自动创建在项目目录中。

## 手动启动

```bash
cd Bad_Messages_In_WeChat_Groups
pip install -r requirements.txt
python run.py
```

然后访问终端显示的 URL（默认 `http://127.0.0.1:8000`）。

## 管理界面

打开浏览器后，通过左侧导航栏管理：

| 标签页 | 功能 |
|--------|------|
| **状态** | 监控器运行状态、群组/管理员统计、启动/停止监控 |
| **群组** | 管理被监控的微信群（添加/删除/启用/停用） |
| **管理员** | 配置管理员昵称和微信号（用于接收通知） |
| **关键词** | 编辑关键词列表（每行一个） |
| **设置** | LLM 模型参数、监控间隔等 |
| **告警** | 查看历史检测记录和 LLM 判定结果 |

## 配置文件

### 关键词 (`keywords.txt`)

每行一个关键词，支持中文和英文：

```
代写
代考
诈骗
加群
免费领
```

### 环境变量 (`.env`)

```env
LLM_BASE_URL=https://api.openai.com/v1    # API 地址
LLM_API_KEY=sk-xxx                         # API 密钥
LLM_MODEL=gpt-4o-mini                      # 模型名称
```

### Web 界面设置

通过浏览器的"设置"页面可配置 LLM 参数，优先级高于 `.env` 文件。

## 通知方式

管理员会收到两种形式的通知：

1. **群内 @提及** — 在所有被监控群中一次性 @所有管理员，不带额外文字
2. **私信通知** — 通过微信号搜索并发送详细内容，包含群聊名称、发送者、匹配关键词、消息原文

## 项目结构

```
Bad_Messages_In_WeChat_Groups/
├── run.py                     # 入口脚本
├── start.bat                  # 项目内启动脚本
├── start_master.bat           # ← 请将此文件放到父目录
├── keywords.txt               # 关键词文件
├── .env                       # 环境变量配置
├── requirements.txt           # Python 依赖
├── app/
│   ├── main.py                # FastAPI 应用
│   ├── database.py            # 异步 SQLAlchemy 引擎
│   ├── models.py              # ORM 数据模型
│   ├── schemas.py             # Pydantic 数据模型
│   ├── config.py              # 配置加载器
│   ├── router.py              # API 路由
│   ├── services/
│   │   ├── wechat_service.py      # wxauto 封装
│   │   ├── llm_service.py         # LLM API 调用
│   │   ├── notification_service.py # 通知逻辑
│   │   └── monitor_service.py     # 后台监控线程
│   └── static/
│       ├── index.html         # Web 界面
│       ├── style.css          # 暗色主题
│       └── app.js             # 前端逻辑
```

## 开源协议

Apache License 2.0

Copyright 2026

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

## 免责声明

本项目仅供学习和研究使用。使用本项目监控微信群聊时，请遵守当地法律法规和微信用户协议。开发者不对因使用本项目产生的任何问题承担责任。
