import os
import sys
import queue
import threading
import subprocess
import customtkinter as ctk
from dotenv import load_dotenv, set_key

# --- 环境变量加载 ---
ENV_PATH = "env"
load_dotenv(dotenv_path=ENV_PATH)

# 尝试导入核心业务流
try:
    from world_builder import run_world_builder
    from volume_planner import run_volume_planner, plan_macro_outlines
    from scene_writer import run_scene_writer
    from utils.config import wait_for_background_tasks
    import utils.config as sys_config
    
    # --- V3 微内核引擎 ---
    from core.novel_context import NovelContext
    from core.plugin_manager import PluginManager
    from utils.workspace import WorkspaceManager
except ImportError as e:
    print(f"[WARN] 导入核心模块失败: {e}")

# ==========================================
# 默认提示词常量
# ==========================================
DEFAULT_PROMPT_S01 = "核心创意：{logline}\n\n请为这个网文世界生成 `{category}` 相关设定。必须详实、有网文爽感和深度。"
DEFAULT_PROMPT_S02 = """你是一个网文白金主编。当前任务是为指定卷做微观打点(Beat Sheet)。
【任务要求】:
1. 生成指定范围的剧情点。
2. 每章必须拆分为 3 到 4 个 Scene Beats。
3. 每个 Beat 的 plot_summary 必须明确说明当前场景的角色动作和目的。"""
DEFAULT_PROMPT_S03_WRITER = """请严格按照小说正文格式展开这段剧情。
要求：
- 直接输出正文，不要带有分析、总结等任何多余的废话。
- 目标字数需要严格控制，绝不能过度水字数。
- 注重画面感、动作描写与对话张力。"""
DEFAULT_PROMPT_S03_EDITOR = """你是一个网文主编。请消除场景拼接草稿之间的割裂感，平滑自然段过渡。
要求：
1. 绝对不要大量删减动作和对话细节（保持原字数 95% 以上）。
2. 修复可能出现的视角跳跃。
3. 润色结尾，留下强烈的网文悬念（断章感）。
4. 直接输出小说的正文内容，绝不要输出分析、总结、多余的标记。"""

# ==========================================
# 终端输出重定向
# ==========================================
class TextRedirector:
    def __init__(self, log_queue):
        self.log_queue = log_queue
    def write(self, text):
        if text:
            self.log_queue.put(text)
    def flush(self):
        pass

# ==========================================
# 主窗口
# ==========================================
class NovelClaudeGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Novel-Claude V3 智能网文生成工作站")
        self.geometry("1300x850")
        self.minsize(1100, 700)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self._task_running = False
        self._all_buttons = []

        # 布局
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=3)
        self.grid_rowconfigure(1, weight=2)

        self._build_sidebar()
        self._build_main_tabs()
        self._build_terminal()

        # 终端重定向
        self.log_queue = queue.Queue()
        sys.stdout = TextRedirector(self.log_queue)
        sys.stderr = TextRedirector(self.log_queue)
        # 初始化 V3 微内核插件系统
        self._init_v3_kernel()

        # 启动日志轮询
        self.after(80, self._poll_log_queue)

        print("═" * 60)
        print("  🚀 Novel-Claude V3 微内核引擎已启动")
        print(f"  📂 当前项目: {os.getenv('NOVEL_NAME', '默认')}")
        print(f"  🤖 当前模型: {os.getenv('MODEL_ID', 'glm-4.6v')}")
        loaded_count = len(self.novel_context.active_skills) if hasattr(self, 'novel_context') else 0
        print(f"  🔌 已加载插件: {loaded_count} 个")
        print("═" * 60)

    # ──────────────────────────────────
    #  左侧边栏
    # ──────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkScrollableFrame(self, width=280, corner_radius=0)
        sb.grid(row=0, column=0, rowspan=2, sticky="nsew")

        # Logo
        ctk.CTkLabel(sb, text="📖 Novel-Claude", font=ctk.CTkFont(size=22, weight="bold")).pack(padx=20, pady=(18, 4))
        ctk.CTkLabel(sb, text="V3 微内核 · 插件生态引擎", font=ctk.CTkFont(size=11), text_color="gray60").pack(padx=20, pady=(0, 12))

        # ── API 配置 ──
        self._sidebar_section(sb, "🔗 API 配置")

        ctk.CTkLabel(sb, text="Provider:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.provider_var = ctk.StringVar(value=os.getenv("LLM_PROVIDER", "zhipu"))
        self.provider_menu = ctk.CTkOptionMenu(sb, variable=self.provider_var, values=["zhipu", "ollama", "custom"], command=self._on_provider_change, width=240)
        self.provider_menu.pack(padx=20, pady=(2, 8))

        ctk.CTkLabel(sb, text="Base URL:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.url_entry = ctk.CTkEntry(sb, width=240)
        self.url_entry.pack(padx=20, pady=(2, 8))
        self.url_entry.insert(0, os.getenv("ANTHROPIC_BASE_URL", "https://open.bigmodel.cn/api/anthropic"))

        ctk.CTkLabel(sb, text="API Key:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.key_entry = ctk.CTkEntry(sb, width=240, show="•")
        self.key_entry.pack(padx=20, pady=(2, 8))
        self.key_entry.insert(0, os.getenv("ANTHROPIC_API_KEY", ""))

        ctk.CTkLabel(sb, text="主模型 ID:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.model_entry = ctk.CTkEntry(sb, width=240)
        self.model_entry.pack(padx=20, pady=(2, 8))
        self.model_entry.insert(0, os.getenv("MODEL_ID", "glm-4.6v"))

        ctk.CTkLabel(sb, text="Flash 模型 ID:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.flash_model_entry = ctk.CTkEntry(sb, width=240)
        self.flash_model_entry.pack(padx=20, pady=(2, 8))
        self.flash_model_entry.insert(0, os.getenv("FLASH_MODEL_ID", "glm-4.6v"))

        # ── 生成参数 ──
        self._sidebar_section(sb, "⚙️ 生成参数")

        ctk.CTkLabel(sb, text="项目名称 (NOVEL_NAME):", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.novel_name_entry = ctk.CTkEntry(sb, width=240, placeholder_text="留空则使用默认 .novel 目录")
        self.novel_name_entry.pack(padx=20, pady=(2, 8))
        self.novel_name_entry.insert(0, os.getenv("NOVEL_NAME", ""))

        ctk.CTkLabel(sb, text=f"每章目标字数: {os.getenv('CHAPTER_TARGET_WORDS', '5000')}", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.words_slider = ctk.CTkSlider(sb, from_=2000, to=10000, number_of_steps=16, width=240, command=self._on_words_slider)
        self.words_slider.pack(padx=20, pady=(2, 4))
        self.words_slider.set(int(os.getenv("CHAPTER_TARGET_WORDS", "5000")))
        self.words_label = sb.winfo_children()[-2]  # reference to the label above slider

        row_frame = ctk.CTkFrame(sb, fg_color="transparent")
        row_frame.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_frame, text="总卷数:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.total_vols_entry = ctk.CTkEntry(row_frame, width=60)
        self.total_vols_entry.pack(side="left", padx=(4, 16))
        self.total_vols_entry.insert(0, os.getenv("TOTAL_VOLUMES", "10"))
        ctk.CTkLabel(row_frame, text="每卷章数:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.chaps_per_vol_entry = ctk.CTkEntry(row_frame, width=60)
        self.chaps_per_vol_entry.pack(side="left", padx=4)
        self.chaps_per_vol_entry.insert(0, os.getenv("CHAPTERS_PER_VOLUME", "50"))

        row_frame2 = ctk.CTkFrame(sb, fg_color="transparent")
        row_frame2.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_frame2, text="Chunk Size:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.chunk_entry = ctk.CTkEntry(row_frame2, width=60)
        self.chunk_entry.pack(side="left", padx=4)
        self.chunk_entry.insert(0, os.getenv("CHUNK_SIZE", "5"))

        # ── 按钮区 ──
        self._sidebar_section(sb, "")
        save_btn = ctk.CTkButton(sb, text="💾 保存全部配置", command=self._save_all_config, fg_color="#2563EB", hover_color="#1D4ED8", height=36)
        save_btn.pack(padx=20, pady=(0, 10), fill="x")

        # ── 插件快捷入口 ──
        self._sidebar_section(sb, "🔌 插件快捷")
        self.skill_status_label = ctk.CTkLabel(sb, text="已加载: 0 个插件", font=ctk.CTkFont(size=11), text_color="#60A5FA")
        self.skill_status_label.pack(anchor="w", padx=20, pady=(0, 4))
        reload_btn = ctk.CTkButton(sb, text="🔄 重载全部插件", command=self._reload_all_skills, fg_color="#9333EA", hover_color="#7E22CE", height=32)
        reload_btn.pack(padx=20, pady=(0, 4), fill="x")

        # 主题切换
        theme_frame = ctk.CTkFrame(sb, fg_color="transparent")
        theme_frame.pack(fill="x", padx=20, pady=(10, 14))
        ctk.CTkLabel(theme_frame, text="🌙 主题:", font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkOptionMenu(theme_frame, values=["Dark", "Light", "System"], command=lambda v: ctk.set_appearance_mode(v), width=100).pack(side="right")

    # ──────────────────────────────────
    #  主内容区 (4 Tabs)
    # ──────────────────────────────────
    def _build_main_tabs(self):
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.grid(row=0, column=1, padx=(0, 16), pady=(10, 4), sticky="nsew")

        tab_wf = self.tabview.add("📝 工作流")
        tab_skills = self.tabview.add("🔌 Skills 插件")
        tab_cfg = self.tabview.add("⚙️ 环境配置")
        tab_prompt = self.tabview.add("✏️ 提示词工程")
        tab_batch = self.tabview.add("📦 Batch 批量")

        self._build_tab_workflow(tab_wf)
        self._build_tab_skills(tab_skills)
        self._build_tab_config(tab_cfg)
        self._build_tab_prompts(tab_prompt)
        self._build_tab_batch(tab_batch)

    def _build_tab_workflow(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # 进度状态
        self.status_label = ctk.CTkLabel(scroll, text="⏸️ 就绪 — 等待任务启动", font=ctk.CTkFont(size=13, weight="bold"), text_color="#60A5FA")
        self.status_label.pack(anchor="w", padx=10, pady=(8, 12))

        # ── 阶段 1 ──
        f1 = self._card(scroll, "🌍 阶段 1：世界观初始化 (Init)")
        ctk.CTkLabel(f1, text="输入你的核心创意 Logline：", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=(8, 2))
        self.logline_entry = ctk.CTkEntry(f1, placeholder_text="例如：一个依靠植入赛博义体获取灵根的修仙废柴的故事...", height=34)
        self.logline_entry.pack(fill="x", padx=12, pady=(0, 8))
        btn1 = ctk.CTkButton(f1, text="🚀 构建世界观", height=34, command=self._run_init)
        btn1.pack(anchor="e", padx=12, pady=(0, 10))
        self._all_buttons.append(btn1)

        # ── 阶段 2 ──
        f2 = self._card(scroll, "📋 阶段 2：大纲与分卷规划 (Plan)")
        row2 = ctk.CTkFrame(f2, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=8)
        btn_macro = ctk.CTkButton(row2, text="📝 生成全局宏观大纲", fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE"), height=34, command=self._run_macro_plan)
        btn_macro.pack(side="left", padx=(0, 16))
        self._all_buttons.append(btn_macro)
        ctk.CTkLabel(row2, text="目标卷号:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.vol_plan_entry = ctk.CTkEntry(row2, width=70, height=34)
        self.vol_plan_entry.insert(0, "1")
        self.vol_plan_entry.pack(side="left", padx=(0, 8))
        btn_vol = ctk.CTkButton(row2, text="🎯 生成单卷章节细纲", height=34, command=self._run_vol_plan)
        btn_vol.pack(side="left")
        self._all_buttons.append(btn_vol)

        # ── 阶段 3 ──
        f3 = self._card(scroll, "✍️ 阶段 3：场景正文写作 (Write)")
        row3 = ctk.CTkFrame(f3, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row3, text="卷号:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.vol_write_entry = ctk.CTkEntry(row3, width=60, height=34)
        self.vol_write_entry.insert(0, "1")
        self.vol_write_entry.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(row3, text="章节范围:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.chap_write_entry = ctk.CTkEntry(row3, width=100, height=34, placeholder_text="如 1-5")
        self.chap_write_entry.insert(0, "1-3")
        self.chap_write_entry.pack(side="left", padx=(0, 12))
        btn_write = ctk.CTkButton(row3, text="✍️ 启动执笔集群", height=34, fg_color="#16A34A", hover_color="#15803D", command=self._run_write)
        btn_write.pack(side="left")
        self._all_buttons.append(btn_write)

        # ── 工具区 ──
        f4 = self._card(scroll, "🔧 工具箱")
        row4 = ctk.CTkFrame(f4, fg_color="transparent")
        row4.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row4, text="卷号:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.reindex_vol_entry = ctk.CTkEntry(row4, width=60, height=34)
        self.reindex_vol_entry.insert(0, "1")
        self.reindex_vol_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row4, text="章节:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.reindex_chap_entry = ctk.CTkEntry(row4, width=100, height=34, placeholder_text="如 1-5")
        self.reindex_chap_entry.insert(0, "1-5")
        self.reindex_chap_entry.pack(side="left", padx=(0, 8))
        btn_reindex = ctk.CTkButton(row4, text="🔄 重建 RAG 记忆", height=34, fg_color="#9333EA", hover_color="#7E22CE", command=self._run_reindex)
        btn_reindex.pack(side="left")
        self._all_buttons.append(btn_reindex)

    # ──────────────────────────────────
    #  Skills 插件管理 Tab (V3 核心)
    # ──────────────────────────────────
    def _build_tab_skills(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # ── 已加载的插件列表 ──
        f_loaded = self._card(scroll, "📋 已加载的插件 (Skills)")
        ctk.CTkLabel(f_loaded, text="以下插件已被 PluginManager 自动扫描并挂载到 EventBus:",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(anchor="w", padx=12, pady=(4, 4))
        self.skills_list_frame = ctk.CTkFrame(f_loaded, fg_color="transparent")
        self.skills_list_frame.pack(fill="x", padx=12, pady=(0, 8))
        self._refresh_skills_list()

        btn_row = ctk.CTkFrame(f_loaded, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(btn_row, text="🔄 刷新列表", width=130, height=32, command=self._refresh_skills_list).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="♻️ 热重载全部插件", width=160, height=32, fg_color="#9333EA", hover_color="#7E22CE",
                      command=self._reload_all_skills).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="📂 打开 skills 目录", width=150, height=32, fg_color="transparent", border_width=2,
                      text_color=("gray10", "#DCE4EE"),
                      command=lambda: os.startfile(os.path.abspath("skills"))).pack(side="left")

        # ── 单个插件热重载 ──
        f_single = self._card(scroll, "🔧 单个插件热重载")
        ctk.CTkLabel(f_single, text="输入 skills/ 下的文件夹名进行单插件热更新:",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(anchor="w", padx=12, pady=(4, 2))
        row_single = ctk.CTkFrame(f_single, fg_color="transparent")
        row_single.pack(fill="x", padx=12, pady=(0, 10))
        self.single_skill_entry = ctk.CTkEntry(row_single, height=34, placeholder_text="如 core_memory_rag")
        self.single_skill_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(row_single, text="♻️ 热重载", height=34, fg_color="#F59E0B", hover_color="#D97706",
                      command=self._hot_reload_single_skill).pack(side="right")

        # ── SkillBuilder Agent (Meta-Generation) ──
        f_builder = self._card(scroll, "🤖 SkillBuilder Agent (Meta-Generation)")
        ctk.CTkLabel(f_builder, text="用自然语言描述你需要的插件功能，大模型会自动生成合法的 BaseSkill 子类代码并热重载:",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(anchor="w", padx=12, pady=(4, 2))
        self.agent_intent_entry = ctk.CTkTextbox(f_builder, height=80, font=ctk.CTkFont(family="Consolas", size=12))
        self.agent_intent_entry.pack(fill="x", padx=12, pady=(4, 8))
        self.agent_intent_entry.insert("0.0", "帮我写一个 Skill，在每次生成前自动注入一句 '主角很帅' 到 prompt 中")
        agent_btn = ctk.CTkButton(f_builder, text="✨ 召唤 SkillBuilder Agent 生成插件",
                                  command=self._run_skill_builder, fg_color="#F59E0B", hover_color="#D97706", height=36)
        agent_btn.pack(anchor="e", padx=12, pady=(0, 10))
        self._all_buttons.append(agent_btn)

        # ── 开发指南卡片 ──
        f_guide = self._card(scroll, "📚 手动开发指南")
        guide_text = """要手动开发一个 V3 插件 (Skill)，请按以下步骤操作：

1. 在 skills/ 目录下创建一个新文件夹，如 skills/my_awesome_skill/
2. 在该文件夹内创建 skill.py 文件
3. 编写一个继承 BaseSkill 的类，覆写你需要的生命周期钩子：
   - on_init()：初始化资源
   - on_before_scene_write()：在生成前注入上下文
   - on_after_scene_write()：生成后执行清理/统计
   - on_volume_planning()：拦截并修改分卷大纲
   - get_llm_tools()：注册 LLM 可调用工具
4. 保存后点击上方「♻️ 热重载全部插件」即可生效！

也可以通过 CLI：uv run python cli.py skills list"""
        guide_box = ctk.CTkTextbox(f_guide, height=180, font=ctk.CTkFont(family="Consolas", size=11))
        guide_box.pack(fill="x", padx=12, pady=(4, 10))
        guide_box.insert("0.0", guide_text)
        guide_box.configure(state="disabled")

    def _refresh_skills_list(self):
        """刷新已加载插件的列表显示"""
        for widget in self.skills_list_frame.winfo_children():
            widget.destroy()

        if not hasattr(self, 'novel_context') or not self.novel_context.active_skills:
            ctk.CTkLabel(self.skills_list_frame, text="  (暂无已加载的插件)",
                         font=ctk.CTkFont(size=11), text_color="gray50").pack(anchor="w")
            if hasattr(self, 'skill_status_label'):
                self.skill_status_label.configure(text="已加载: 0 个插件")
            return

        for name, skill in self.novel_context.active_skills.items():
            row = ctk.CTkFrame(self.skills_list_frame, fg_color=("gray88", "gray20"), corner_radius=6)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"  🟢 {skill.name}", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=8, pady=6)
            ctk.CTkLabel(row, text=f"({name}/)", font=ctk.CTkFont(size=10), text_color="gray50").pack(side="left")
            ctk.CTkButton(row, text="♻️", width=30, height=26, fg_color="transparent", border_width=1,
                          text_color=("gray10", "#DCE4EE"),
                          command=lambda n=name: self._hot_reload_one(n)).pack(side="right", padx=6, pady=4)

        count = len(self.novel_context.active_skills)
        if hasattr(self, 'skill_status_label'):
            self.skill_status_label.configure(text=f"已加载: {count} 个插件")

    def _hot_reload_one(self, name):
        self.plugin_manager.hot_reload(name)
        self._refresh_skills_list()

    def _hot_reload_single_skill(self):
        name = self.single_skill_entry.get().strip()
        if not name:
            print("[WARN] 请输入插件文件夹名！")
            return
        self.plugin_manager.hot_reload(name)
        self._refresh_skills_list()

    def _reload_all_skills(self):
        print("[INFO] 正在重载全部插件...")
        from core.event_bus import event_bus
        for skill in list(self.novel_context.active_skills.values()):
            event_bus.unregister(skill)
        self.novel_context.active_skills.clear()
        self.plugin_manager.loaded_modules.clear()
        self.plugin_manager.scan_and_load()
        self._refresh_skills_list()
        print("[✓] 全部插件已重载！")

    def _build_tab_config(self, parent):
        """环境配置总览（只读预览模式）"""
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        ctk.CTkLabel(scroll, text="当前 env 文件内容（修改请使用左侧面板后点击保存）", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10, pady=(10, 4))

        self.env_preview = ctk.CTkTextbox(scroll, font=ctk.CTkFont(family="Consolas", size=12), height=250)
        self.env_preview.pack(fill="both", expand=True, padx=10, pady=8)
        self._refresh_env_preview()

        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(btn_row, text="🔄 刷新预览", width=140, command=self._refresh_env_preview).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="📂 打开 env 文件", width=140, command=lambda: os.startfile(os.path.abspath(ENV_PATH)) if os.path.exists(ENV_PATH) else print("[WARN] env 文件不存在")).pack(side="left")

    def _build_tab_prompts(self, parent):
        """提示词工程 Tab：4 个可编辑的核心提示词"""
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        prompts_config = [
            ("s01", "🌍 世界观生成提示词 (world_builder)", "PROMPT_S01_WORLDBUILD", DEFAULT_PROMPT_S01),
            ("s02", "📋 章节打点提示词 (volume_planner)", "PROMPT_S02_BEATS", DEFAULT_PROMPT_S02),
            ("s03w", "✍️ 场景写作提示词 (scene_writer)", "PROMPT_S03_WRITER", DEFAULT_PROMPT_S03_WRITER),
            ("s03e", "🖊️ Editor 润色提示词 (editor)", "PROMPT_S03_EDITOR", DEFAULT_PROMPT_S03_EDITOR),
        ]

        self.prompt_boxes = {}
        for key, title, env_key, default in prompts_config:
            f = self._card(scroll, title)
            box = ctk.CTkTextbox(f, height=120, font=ctk.CTkFont(family="Consolas", size=12))
            box.pack(fill="x", padx=12, pady=(4, 4))
            box.insert("0.0", os.getenv(env_key, default))
            self.prompt_boxes[env_key] = box
            ctk.CTkButton(f, text=f"💾 保存 {key} 提示词", width=160, height=30, command=lambda ek=env_key: self._save_single_prompt(ek)).pack(anchor="e", padx=12, pady=(0, 8))

    def _build_tab_batch(self, parent):
        """Batch 批量模式 Tab"""
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # 步骤 1
        f1 = self._card(scroll, "📦 步骤 1：构建 JSONL 请求文件")
        row1 = ctk.CTkFrame(f1, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row1, text="卷号:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.batch_vol_entry = ctk.CTkEntry(row1, width=60, height=34)
        self.batch_vol_entry.insert(0, "1")
        self.batch_vol_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row1, text="章节范围:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.batch_chap_entry = ctk.CTkEntry(row1, width=100, height=34, placeholder_text="1-50")
        self.batch_chap_entry.insert(0, "1-50")
        self.batch_chap_entry.pack(side="left", padx=(0, 8))
        btn_build = ctk.CTkButton(row1, text="🔨 构建 JSONL", height=34, command=self._run_batch_build)
        btn_build.pack(side="left")
        self._all_buttons.append(btn_build)

        # 步骤 2
        f2 = self._card(scroll, "🚀 步骤 2：提交到云端")
        row2 = ctk.CTkFrame(f2, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row2, text="JSONL 路径:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.batch_jsonl_entry = ctk.CTkEntry(row2, height=34, placeholder_text=".novel/batch_jobs/vol_01_ch_1_50_req.jsonl")
        self.batch_jsonl_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn_submit = ctk.CTkButton(row2, text="📤 提交任务", height=34, command=self._run_batch_submit)
        btn_submit.pack(side="right")
        self._all_buttons.append(btn_submit)

        # 步骤 3
        f3 = self._card(scroll, "🔄 步骤 3：同步结果")
        row3 = ctk.CTkFrame(f3, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row3, text="Batch ID:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.batch_id_entry = ctk.CTkEntry(row3, height=34, placeholder_text="batch_xxx")
        self.batch_id_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn_sync = ctk.CTkButton(row3, text="⬇️ 同步结果", height=34, fg_color="#16A34A", hover_color="#15803D", command=self._run_batch_sync)
        btn_sync.pack(side="right")
        self._all_buttons.append(btn_sync)

    # ──────────────────────────────────
    #  底部终端
    # ──────────────────────────────────
    def _build_terminal(self):
        tf = ctk.CTkFrame(self, corner_radius=10)
        tf.grid(row=1, column=1, padx=(0, 16), pady=(4, 12), sticky="nsew")
        tf.grid_columnconfigure(0, weight=1)
        tf.grid_rowconfigure(1, weight=1)

        # 顶栏
        top = ctk.CTkFrame(tf, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        ctk.CTkLabel(top, text="💻 系统控制台", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="🗑️ 清屏", width=70, height=28, fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE"), command=self._clear_terminal).pack(side="right")

        # 输出区
        self.console_text = ctk.CTkTextbox(tf, font=ctk.CTkFont(family="Consolas", size=12), wrap="word", state="disabled")
        self.console_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(2, 4))

        # 命令输入行
        cmd_frame = ctk.CTkFrame(tf, fg_color="transparent")
        cmd_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
        cmd_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(cmd_frame, text="❯", font=ctk.CTkFont(family="Consolas", size=14, weight="bold"), text_color="#60A5FA").grid(row=0, column=0, padx=(0, 6))
        self.cmd_entry = ctk.CTkEntry(cmd_frame, font=ctk.CTkFont(family="Consolas", size=12), height=32, placeholder_text="输入 CLI 命令，如：uv run python cli.py plan --volume 1")
        self.cmd_entry.grid(row=0, column=1, sticky="ew")
        self.cmd_entry.bind("<Return>", self._exec_cmd)
        ctk.CTkButton(cmd_frame, text="执行", width=60, height=32, command=self._exec_cmd).grid(row=0, column=2, padx=(6, 0))

    # ──────────────────────────────────
    #  UI 辅助方法
    # ──────────────────────────────────
    def _sidebar_section(self, parent, title):
        if title:
            ctk.CTkLabel(parent, text="─" * 30, text_color="gray40").pack(padx=20, pady=(10, 0))
            ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(4, 6))

    def _card(self, parent, title):
        f = ctk.CTkFrame(parent, corner_radius=8)
        f.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=12, pady=(10, 2))
        return f

    def _on_words_slider(self, value):
        v = int(value)
        self.words_label.configure(text=f"每章目标字数: {v}")

    def _on_provider_change(self, choice):
        if choice == "ollama":
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, "http://localhost:11434/v1")
            self.key_entry.delete(0, "end")
            self.key_entry.insert(0, "ollama")
            self.model_entry.delete(0, "end")
            self.model_entry.insert(0, "qwen2.5:8b")
        elif choice == "zhipu":
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, "https://open.bigmodel.cn/api/anthropic")

    def _poll_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.console_text.configure(state="normal")
            self.console_text.insert("end", msg)
            self.console_text.see("end")
            self.console_text.configure(state="disabled")
        self.after(60, self._poll_log_queue)

    def _clear_terminal(self):
        self.console_text.configure(state="normal")
        self.console_text.delete("0.0", "end")
        self.console_text.configure(state="disabled")

    def _refresh_env_preview(self):
        self.env_preview.configure(state="normal")
        self.env_preview.delete("0.0", "end")
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                self.env_preview.insert("0.0", f.read())
        except FileNotFoundError:
            self.env_preview.insert("0.0", "(env 文件不存在)")
        self.env_preview.configure(state="disabled")

    # ──────────────────────────────────
    #  配置保存
    # ──────────────────────────────────
    def _save_all_config(self):
        pairs = {
            "ANTHROPIC_BASE_URL": self.url_entry.get(),
            "ANTHROPIC_API_KEY": self.key_entry.get(),
            "MODEL_ID": self.model_entry.get(),
            "FLASH_MODEL_ID": self.flash_model_entry.get(),
            "NOVEL_NAME": self.novel_name_entry.get().strip(),
            "CHAPTER_TARGET_WORDS": str(int(self.words_slider.get())),
            "TOTAL_VOLUMES": self.total_vols_entry.get().strip(),
            "CHAPTERS_PER_VOLUME": self.chaps_per_vol_entry.get().strip(),
            "CHUNK_SIZE": self.chunk_entry.get().strip(),
            "LLM_PROVIDER": self.provider_var.get(),
        }
        for k, v in pairs.items():
            set_key(ENV_PATH, k, v)
            os.environ[k] = v
            
        import importlib
        importlib.reload(sys_config)
        self._init_v3_kernel()
        
        self._refresh_env_preview()
        print("[✓] 全部配置已保存并重载 V3 微内核。")

    def _init_v3_kernel(self):
        """挂载 NovelContext 和 PluginManager"""
        print("[INFO] 正在挂载 V3 微内核...")
        self.workspace_mgr = WorkspaceManager(sys_config.NOVEL_DIR)
        self.novel_context = NovelContext(self.workspace_mgr)
        self.plugin_manager = PluginManager(self.novel_context)
        self.plugin_manager.scan_and_load()
        # 刷新 UI 上的插件列表
        if hasattr(self, 'skills_list_frame'):
            self._refresh_skills_list()

    def _save_single_prompt(self, env_key):
        box = self.prompt_boxes[env_key]
        text = box.get("0.0", "end").strip()
        set_key(ENV_PATH, env_key, text)
        os.environ[env_key] = text
        print(f"[✓] 提示词 {env_key} 已保存！")

    # ──────────────────────────────────
    #  命令执行
    # ──────────────────────────────────
    def _exec_cmd(self, event=None):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return
        self.cmd_entry.delete(0, "end")
        print(f"\n❯ {cmd}")

        def run():
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.getcwd(), encoding="utf-8", errors="replace")
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)
            except Exception as e:
                print(f"[ERROR] 命令执行失败: {e}")

        threading.Thread(target=run, daemon=True).start()

    # ──────────────────────────────────
    #  任务调度（线程安全）
    # ──────────────────────────────────
    def _run_in_thread(self, label, task_func, *args):
        if self._task_running:
            print("[WARN] 有任务正在运行中，请等待完成后再启动新任务。")
            return
        self._task_running = True
        for btn in self._all_buttons:
            btn.configure(state="disabled")
        self.status_label.configure(text=f"⏳ {label} — 运行中...", text_color="#FBBF24")

        def wrapper():
            try:
                task_func(*args)
                wait_for_background_tasks()
                print(f"\n[🎉] {label} 全部完成！\n")
                self.status_label.configure(text=f"✅ {label} — 已完成", text_color="#34D399")
            except Exception as e:
                print(f"\n[🚨 Error] {label} 失败: {e}\n")
                self.status_label.configure(text=f"❌ {label} — 失败", text_color="#F87171")
            finally:
                self._task_running = False
                for btn in self._all_buttons:
                    btn.configure(state="normal")

        threading.Thread(target=wrapper, daemon=True).start()

    def _run_skill_builder(self):
        intent = self.agent_intent_entry.get("0.0", "end").strip()
        if not intent:
            print("[WARN] 请先输入开发需求！")
            return
            
        def builder_task():
            from core.agents.skill_builder_agent import SkillBuilderAgent
            agent = SkillBuilderAgent(self.novel_context, self.plugin_manager)
            agent.build_skill(intent)
            self._refresh_skills_list()
            
        self._run_in_thread("Meta-Generation", builder_task)

    # ──────────────────────────────────
    #  工作流按钮回调
    # ──────────────────────────────────
    def _run_init(self):
        logline = self.logline_entry.get().strip()
        if not logline:
            print("[WARN] 请先输入核心创意！")
            return
        self._run_in_thread("世界观初始化", run_world_builder, logline)

    def _run_macro_plan(self):
        self._run_in_thread("宏观大纲生成", plan_macro_outlines)

    def _run_vol_plan(self):
        vol = self.vol_plan_entry.get().strip()
        if not vol.isdigit():
            print("[WARN] 目标卷号必须是整数！")
            return
        self._run_in_thread(f"卷 {vol} 章节细纲生成", run_volume_planner, int(vol))

    def _run_write(self):
        vol = self.vol_write_entry.get().strip()
        chaps = self.chap_write_entry.get().strip()
        if not vol.isdigit():
            print("[WARN] 卷号必须是数字！")
            return
        try:
            if '-' in chaps:
                start, end = map(int, chaps.split('-'))
            else:
                start = end = int(chaps)
        except ValueError:
            print("[WARN] 章节范围格式错误，应为如 '1-5'")
            return
        self._run_in_thread(f"卷 {vol} 第 {chaps} 章写作", run_scene_writer, int(vol), start, end)

    def _run_reindex(self):
        vol = self.reindex_vol_entry.get().strip()
        chaps = self.reindex_chap_entry.get().strip()
        if not vol.isdigit():
            print("[WARN] 卷号必须是数字！")
            return
        try:
            if '-' in chaps:
                start, end = map(int, chaps.split('-'))
            else:
                start = end = int(chaps)
        except ValueError:
            print("[WARN] 章节范围格式错误")
            return

        def reindex_task():
            from core.event_bus import event_bus
            from utils.config import MANUSCRIPTS_DIR
            for chap in range(start, end + 1):
                path = os.path.join(MANUSCRIPTS_DIR, f"vol_{int(vol):02d}", f"ch_{chap:03d}_final.md")
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    print(f"[REINDEX] 正在补全第 {chap} 章的记忆...")
                    beat_mock = {"chapter_id": chap, "beats": []}
                    event_bus.emit("on_after_scene_write", beat_mock, content)
                else:
                    print(f"[WARN] 找不到成稿文件: {path}")

        self._run_in_thread(f"RAG 记忆重建 (卷{vol} 章{chaps})", reindex_task)

    def _run_batch_build(self):
        vol = self.batch_vol_entry.get().strip()
        chaps = self.batch_chap_entry.get().strip()
        if not vol.isdigit():
            print("[WARN] 卷号必须是数字！")
            return
        try:
            if '-' in chaps:
                start, end = map(int, chaps.split('-'))
            else:
                start = end = int(chaps)
        except ValueError:
            print("[WARN] 章节范围格式错误")
            return

        def build_task():
            from scene_writer import generate_batch_jsonl
            from utils.config import BATCH_DIR
            output_path = os.path.join(BATCH_DIR, f"vol_{int(vol):02d}_ch_{start}_{end}_req.jsonl")
            generate_batch_jsonl(int(vol), start, end, output_path)
            self.batch_jsonl_entry.delete(0, "end")
            self.batch_jsonl_entry.insert(0, output_path)

        self._run_in_thread("构建 Batch JSONL", build_task)

    def _run_batch_submit(self):
        jsonl_path = self.batch_jsonl_entry.get().strip()
        if not jsonl_path or not os.path.exists(jsonl_path):
            print(f"[WARN] 找不到文件: {jsonl_path}")
            return

        def submit_task():
            from utils.batch_client import submit_batch_task
            batch_id = submit_batch_task(jsonl_path, desc=f"Submit: {os.path.basename(jsonl_path)}")
            print(f"\n[✓] Batch ID: {batch_id}")
            self.batch_id_entry.delete(0, "end")
            self.batch_id_entry.insert(0, batch_id)

        self._run_in_thread("提交 Batch 任务", submit_task)

    def _run_batch_sync(self):
        batch_id = self.batch_id_entry.get().strip()
        if not batch_id:
            print("[WARN] 请输入 Batch ID！")
            return

        def sync_task():
            from utils.batch_client import get_batch_status, download_batch_results
            from scene_writer import process_batch_results
            from utils.config import BATCH_DIR
            import time
            print(f"[Batch] 正在监听任务 {batch_id}...")
            while True:
                status = get_batch_status(batch_id)
                cs = status.status
                print(f"  > 状态: {cs}")
                if cs == "completed":
                    res_p = os.path.join(BATCH_DIR, f"{batch_id}_results.jsonl")
                    err_p = os.path.join(BATCH_DIR, f"{batch_id}_errors.jsonl")
                    if download_batch_results(batch_id, res_p, err_p):
                        process_batch_results(res_p)
                    return
                elif cs in ["failed", "cancelled", "expired"]:
                    print(f"[ERROR] 任务状态异常: {cs}")
                    return
                time.sleep(60)

        self._run_in_thread("Batch 同步", sync_task)


if __name__ == "__main__":
    app = NovelClaudeGUI()
    app.mainloop()