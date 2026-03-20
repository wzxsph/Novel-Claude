# 📖 Novel-Claude: 网文版简易 Claude Code

**Novel-Claude** 是一个基于 Agentic 工作流的 AI 长篇小说创作系统。它参考了 *Claude Code* 的工程化思路，通过上下文物理隔离、状态持久化和动态 RAG 记忆总线，彻底解决了大模型在创作百万字长文时的“复读机”、“吃书”和“逻辑崩溃”问题。

---

## 核心特质

- **Agent 是打字机，Harness 是编辑部**：模型仅负责局部生成，外围 Python 脚本负责控制逻辑、校验数据和管理上下文。
- **上下文物理隔离 (Context Isolation)**：每个场景（Scene）的生成都在一个完全独立的子进程中完成，写完即销毁，从物理层面杜绝上下文污染。
- **状态绝对持久化 (State Persistence)**：所有世界观、人物卡、分卷大纲均为强类型 JSON 文件，不依赖进程内存储。
- **动态记忆 RAG (Memory Bus)**：利用 ChromaDB 向量数据库，按需倒序检索实体最新状态（如伤势、位置、法宝状态），实现精准的剧情连贯性。

---

## 核心架构 (Harnesses)

### 整体架构设计
```
novel_claude/
├── cli.py                  # 命令行入口（用户唯一交互点）
├── s01_world_builder.py    # 阶段1：世界观设定引擎
├── s02_volume_planner.py   # 阶段2：分卷与章节打点
├── s03_scene_writer.py     # 阶段3：执笔集群（核心爆发引擎）
├── s04_memory_rag.py       # 横切面：动态记忆总线（AOP 风格）
├── utils/
│   ├── config.py           # 环境配置 & 全局路径 & 后台线程管理
│   └── llm_client.py       # LLM 调用封装（三种专用模式）
└── .novel/                 # 运行时数据中心（存储 JSON、MD 和 ChromaDB）
```

### 模块详解

- **s01_world_builder.py (全局设定引擎)**：利用 Pydantic Schema 强制 LLM 生成结构化 JSON。包含势力、等级、人物、规则四类清单。
- **s02_volume_planner.py (规划引擎)**：实现多级拆解。先定 10 卷大纲，再细化具体章节的 Scene Beats。
- **s03_scene_writer.py (执笔集群)**：采用 **Director-Worker 模式**。Director 划分任务，Subagent 在“无菌舱”中独立生成正文，最后由 Director 润色合并。
- **s04_memory_rag.py (动态记忆总线)**：
    - **前置注入 (Pre-Hook)**：提取实体，从 ChromaDB 检索最近章节的状态（倒序检索），注入 XML 背景。
    - **后置刷新 (Post-Hook)**：正文生成后，进行语义分块 (Chunking) 并异步入库。
- **utils/llm_client.py**：封装了针对不同场景的调用模式（`generate_json` / `generate_stream` / `extract_entities`）。
- **utils/config.py**：管理 API Key、目录结构，并提供 `wait_for_background_tasks()` 机制确保进程退出前后台写入任务已完成。

---

## 快速开始

### 1. 环境准备

推荐使用 [uv](https://github.com/astral-sh/uv) 快速部署环境：

```bash
# 创建虚拟环境并安装依赖
uv venv
uv pip install -r requirements.txt
```

### 2. 配置 API Key

在项目根目录下创建 `env` 文件（注意：无后缀名），内容如下：

```env
ANTHROPIC_API_KEY=你的智谱AI_API_KEY
ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
MODEL_ID=glm-4-flash  # 建议初始使用 flash 降低成本
```

> [!IMPORTANT]
> **关于计费**：本项目除了使用对话模型，还会调用 `embedding-3` 向量接口。请确保你的智谱账户中 **“向量模型”** 额度充足。

---

## 使用指南 (CLI)

系统通过极简的命令行接口进行交互：

### 阶段 1：初始化世界观
```bash
uv run python cli.py init "一个赛博朋克与修仙结合的世界，主角通过植入义体获取灵根"
```
完成后请检查 `.novel/settings/` 下生成的 JSON 和 `world_manual.md`。

### 阶段 2：生成分卷与微观细纲
```bash
# 生成 10 卷宏观大纲
uv run python cli.py plan
# 针对第 1 卷生成具体章节的剧情打点 (Beats)
uv run python cli.py plan --volume 1
```

### 阶段 3：启动自动化写作
```bash
# 自动生成第 1 卷的 1 到 5 章
uv run python cli.py write --volume 1 --chapters 1-5
```
生成的成品 Markdown 文件将存放在 `出版级成稿目录/` (或 `.novel/manuscripts/`)。

---

## 项目目录结构

```text
/My_Novel_Project
├── .novel/                     # 核心隐藏控制域（数据中心）
│   ├── settings/               # 全局设定库 (JSON & MD)
│   ├── volumes/                # 分卷规划与章节 Beats
│   ├── manuscripts/            # 正文草稿与成稿区
│   └── memory/                 # ChromaDB 向量数据库
├── utils/                      # 工具类（LLM 客户端、配置管理等）
├── s01_world_builder.py        # 设定引擎
├── s02_volume_planner.py       # 规划引擎
├── s03_scene_writer.py         # 写作引擎
├── s04_memory_rag.py           # 记忆总线
├── cli.py                      # 命令行交互入口
└── requirements.txt            # 依赖清单
```

## 技术反馈与架构建议

- **流式输出**：写作模块接入了 `rich.live`，可在终端实时观察模型“码字”过程。
- **优雅退出**：系统集成了后台线程守护，确保写入向量库的任务在 CLI 退出前全部完成。
- **二次开发**：你可以自由修改 `s03` 的 Prompt 来定制特殊的文风或叙事节奏。

---

*Powered by Antigravity Novel Harness System.*
