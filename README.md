# 📖 Novel-Claude: 网文版简易 Claude Code

**Novel-Claude** 是一个基于 Agentic 工作流的 AI 长篇小说创作系统。它参考了 *Claude Code* 的工程化思路，通过上下文物理隔离、状态持久化和动态 RAG 记忆总线，彻底解决了大模型在创作百万字长文时的“复读机”、“吃书”和“逻辑崩溃”问题。

---

## 核心特质

- **Agent 是打字机，Harness 是编辑部**：模型仅负责局部生成，外围 Python 脚本负责控制逻辑、校验数据和管理上下文。
- **上下文物理隔离 (Context Isolation)**：每个场景（Scene）的生成都在一个完全独立的子进程中完成，从物理层面杜绝上下文污染。
- **多项目隔离 (Multi-Project Support)**：支持通过 `NOVEL_NAME` 环境变量动态切换创作空间，互不干扰。
- **动态记忆 RAG (Rule-based Memory Bus)**：利用 Aho-Corasick 自动机进行毫秒级实体提取，并结合 ChromaDB 检索倒序状态，实现精准剧情连贯。
- **断点续传 (Checkpointing)**：每段场景生成后均实时落盘。如果任务中断，重启后会自动跳过（Skip）已完成部分，节省 API 资费。
- **Batch API 批量生成 (Cost Reduction)**：原生支持 Batch 模式，Token 成本减半，极速吞吐。
- **Editor Agent (Polish Layer)**：内置独立主编智能体，自动抹除场景切割痕迹，确保视角统一与逻辑连贯。

---

## 核心架构 (Harnesses)

### 整体架构设计
```
novel_claude/
├── cli.py                  # 命令行入口（增强型 Help 提示）
├── s01_world_builder.py    # 阶段1：世界观设定引擎
├── s02_volume_planner.py   # 阶段2：分卷规划（内含精确字数归一化算法）
├── s03_scene_writer.py     # 阶段3：执笔集群（含 Editor Agent & Checkpointing）
├── s04_memory_rag.py       # 横切面：记忆总线（基于 Aho-Corasick 毫秒级提取）
├── utils/
│   ├── workspace.py        # [NEW] 线程安全工作区管理 (WorkspaceManager)
│   ├── batch_client.py     # 批量任务封装（提交、轮询、同步）
│   ├── config.py           # 核心配置（含多项目切换逻辑）
│   └── llm_client.py       # LLM 封装（增加 1301 防崩拦截）
└── .novel_{name}/          # 物理隔离的数据中心（自动按项目名创建）
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
MODEL_ID=glm-4-plus  # 推荐模型
NOVEL_NAME=my_first_novel  # [可选] 指定当前项目名称，用于多项目物理隔离
```

### 3. (进阶) 多项目管理
如果你想同时写多本小说，只需在 `env` 中修改 `NOVEL_NAME` 的值。系统会自动将所有数据存入对应的隔离目录（例如 `.novel_my_first_novel`），确保世界观、记忆库和稿件互不干扰。

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

#### 模式 A：实时流式生成（适合短篇生成或单章调试，带终端动态渲染）
```bash
# 自动生成第 1 卷的 1 到 5 章
uv run python cli.py write --volume 1 --chapters 1-5
```

#### 模式 B：大规模批量生成（生产级推荐：半价折扣、极高吞吐量）
```bash
# 1. 构建离线工单库文件 (.jsonl)
uv run python cli.py batch-build --volume 1 --chapters 1-50

# 2. 将包含上百个场景请求的工单推送到智谱云端
uv run python cli.py batch-submit .novel/batch_jobs/vol_01_ch_1_50_req.jsonl
# (命令会输出 Batch ID，例如 batch_xxx，请妥善保存)

# 3. 轮询并同步结果（可放在服务器后台挂机）
# 任务结束后，它会自动下载云端排版好的分段内容，按序组装成章节，并保存到成稿目录
uv run python cli.py batch-sync <刚才返回的_batch_id>
```

### 特殊阶段：手动重补记忆 (Reindex)
如果因为 API 报错或网络中断导致某几章的记忆没有存入向量库：
```bash
# 手动将第 1 卷第 5 章的内容重补进 RAG 记忆中
uv run python cli.py reindex --volume 1 --chapters 5
```

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
