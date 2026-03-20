# 🚀 Novel-Claude V3: Agentic Novel Generation Framework

Novel-Claude 是一个基于大语言模型（如智谱 GLM-4）构建的全自动长篇小说生成管线。在 V3 版本中，它从传统的线性脚本流水线彻底进化为具有极高扩展性的 **微内核 + 插件生态架构 (Microkernel & Plugin Architecture)**。

通过底层的 `EventBus` 事件引擎与动态 `PluginManager`，它支持极其复杂的社区插件生态（Skills）以及基于 ReAct 多轮交互的复杂智能体（Agents）。

## ✨ 核心特性

- **微内核插件系统 (Microkernel & Plugin Ecosystem)**: 所有的附加功能（如动态检索记忆 RAG、战斗合理性检测等）被剥离为主时间线之外的插件（Skills）。支持热重载（Hot-Reload）与错误护航隔离，单个插件崩溃不影响数小时的生成进程。
- **复杂智能体支撑 (Complex Agents)**:
  - 🖋️ **Editor Agent (毒舌主编智能体)**: 在章节生成末尾挂载，启用 ReAct 多轮循环思考对草稿进行严格审稿，自动修复视角跳跃和上下文割裂。
  - 🤖 **Skill Builder Agent (元生成器)**: 系统级别的 Meta-Generation。在 GUI 中输入一行自然语言，系统将**自动撰写并编译合法外挂插件 (Skills)** 落盘生效。
- **多端全覆盖 (GUI & CLI)**: 拥有基于 `customtkinter` 极其美观和现代化的桌面控制台，包含工作流、配置面板、Prompt 自定义、批量生成监控，并附带直接对接 `EventBus` 的内部终端模块。
- **降本提效 (Batch API)**: 原生支持智谱/OpenAI 格式的 Batch API 提交流水线，支持离线 5 折并发生成海量章节，并自动拼接、回调。

---

## 🏗️ 架构总览

整个生成管线被切分为三大核心引擎，引擎之间通过 `NovelContext` 共享白板及 `EventBus` 广播串行：

1. `world_builder.py` (世界观造物主): 根据一句话创意（Logline），构建严格 JSON 格式的背景设定、阵营、人物列表。
2. `volume_planner.py` (分卷派单员): 定制 10 卷纲要，并将大段卷纲拆解为精准到场景的小说打点（Beats），且通过算法强制归一化控制为每章 5000 字精确产出。
3. `scene_writer.py` (执笔车间): 孵化 Subagents 无死角执行场景任务，并交由 Director Agent 进行定稿。

```text
novel_claude/
├── core/                       # 发动机微内核
│   ├── event_bus.py            # 全局事件总线（Fault Tolerance）
│   ├── plugin_manager.py       # 动态插件扫描与加载器
│   ├── base_skill.py           # V3 标准化插件基类
│   ├── novel_context.py        # 共享生命周期上下文
│   └── agents/                 # 复杂推理智能体
├── skills/                     # 插件挂载文件夹
│   └── core_memory_rag/        # 原生的 RAG 记忆流媒体检索引擎
├── world_builder.py            # 核心引擎一：设定构建
├── volume_planner.py           # 核心引擎二：分卷与场景切分
├── scene_writer.py             # 核心引擎三：片段执笔与合并
├── cli.py                      # 终端入口
├── gui.py                      # 桌面化入口
└── utils/                      # 配置文件与 LLM 客户端 API 层
```

---

## 🛠️ 安装与使用

### 1. 环境准备
确保您的 Python >= 3.10。
```bash
# 激活环境后安装依赖
uv pip install -r requirements.txt
```

### 2. 图形界面启动 (推荐)
直接运行并进入现代化桌面端：
```bash
uv run gui.py
```
*在 GUI 中，您可以左侧滑块处配置 API Key（如 `ANTHROPIC_API_KEY` 使用智谱或其他兼容 OpenAI 格式的密钥）、当前书籍名称、生成字数要求等。*

### 3. CLI 快速使用 (Terminal)

如果你喜欢专注黑框终端码字：
```bash
# 阶段 1：一句话初始化世界观
uv run python cli.py init "一个在修真界利用赛博插件强开灵根的科幻转玄幻故事"

# 阶段 2：规划宏观 10 卷的主线大纲
uv run python cli.py plan

# 阶段 3：明确为第 1 卷出具细分到微观单元的 50 章 Scene Beats
uv run python cli.py plan --volume 1

# 阶段 4：召唤执笔集群实时码字生成第 1 卷 1 到 5 章
uv run python cli.py write --volume 1 --chapters 1-5
```

---

## 🔌 V3 插件与外挂生态

V3 引擎的精髓在于无穷无尽的功能扩展。所有的扩展统称为 `Skill`，必须继承 `BaseSkill` 这个协议。插件会被 `PluginManager` 动态接管并且拦截底层 `EventBus` 各个周期的发信事件。

所有合法的插件均放置于 `skills/` 文件夹即可自动被识别生效。

在 `gui.py` 的「🤖 V3 实验区」，您可以直接输入类似：*“帮我写一个技能，拦截每次生成前给里面注入一句话主角很帅”*，由于接入了 `SkillBuilderAgent`，系统会根据内置开发规范文档立刻帮您手搓外挂加载。
