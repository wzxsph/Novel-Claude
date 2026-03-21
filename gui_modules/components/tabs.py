import os
import customtkinter as ctk
from ..constants import DEFAULT_PROMPT_S01, DEFAULT_PROMPT_S02, DEFAULT_PROMPT_S03_WRITER, DEFAULT_PROMPT_S03_EDITOR, ENV_PATH

class MainTabs(ctk.CTkTabview):
    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=10, **kwargs)
        self.app = master
        self._build_main_tabs()

    def _build_main_tabs(self):
        tab_wf = self.add("📝 工作流")
        tab_skills = self.add("🔌 Skills 插件")
        tab_cfg = self.add("⚙️ 环境配置")
        tab_prompt = self.add("✏️ 提示词工程")
        tab_batch = self.add("📦 Batch 批量")
        tab_viewer = self.add("📄 文件查看")
        tab_review = self.add("🔍 AI 审阅")

        self._build_tab_workflow(tab_wf)
        self._build_tab_skills(tab_skills)
        self._build_tab_config(tab_cfg)
        self._build_tab_prompts(tab_prompt)
        self._build_tab_batch(tab_batch)
        self._build_tab_viewer(tab_viewer)
        self._build_tab_review(tab_review)

    def _build_tab_workflow(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # 进度状态
        self.app.status_label = ctk.CTkLabel(scroll, text="⏸️ 就绪 — 等待任务启动", font=ctk.CTkFont(size=13, weight="bold"), text_color="#60A5FA")
        self.app.status_label.pack(anchor="w", padx=10, pady=(8, 12))

        # ── 阶段 1 ──
        f1 = self.app._card(scroll, "🌍 阶段 1：世界观初始化 (Init)")
        ctk.CTkLabel(f1, text="输入你的核心创意 Logline：", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=(8, 2))
        self.app.logline_entry = ctk.CTkEntry(f1, placeholder_text="例如：一个依靠植入赛博义体获取灵根的修仙废柴的故事...", height=34)
        self.app.logline_entry.pack(fill="x", padx=12, pady=(0, 8))
        btn1 = ctk.CTkButton(f1, text="🚀 构建世界观", height=34, command=self.app._run_init)
        btn1.pack(anchor="e", padx=12, pady=(0, 10))
        self.app._all_buttons.append(btn1)

        # ── 阶段 2 ──
        f2 = self.app._card(scroll, "📋 阶段 2：大纲与分卷规划 (Plan)")
        row2 = ctk.CTkFrame(f2, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=8)
        btn_macro = ctk.CTkButton(row2, text="📝 生成全局宏观大纲", fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE"), height=34, command=self.app._run_macro_plan)
        btn_macro.pack(side="left", padx=(0, 16))
        self.app._all_buttons.append(btn_macro)
        ctk.CTkLabel(row2, text="目标卷号:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.app.vol_plan_entry = ctk.CTkEntry(row2, width=70, height=34)
        self.app.vol_plan_entry.insert(0, "1")
        self.app.vol_plan_entry.pack(side="left", padx=(0, 8))
        btn_vol = ctk.CTkButton(row2, text="🎯 生成单卷章节细纲", height=34, command=self.app._run_vol_plan)
        btn_vol.pack(side="left")
        self.app._all_buttons.append(btn_vol)

        # ── 阶段 3 ──
        f3 = self.app._card(scroll, "✍️ 阶段 3：场景正文写作 (Write)")
        row3 = ctk.CTkFrame(f3, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row3, text="卷号:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.app.vol_write_entry = ctk.CTkEntry(row3, width=60, height=34)
        self.app.vol_write_entry.insert(0, "1")
        self.app.vol_write_entry.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(row3, text="章节范围:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.app.chap_write_entry = ctk.CTkEntry(row3, width=100, height=34, placeholder_text="如 1-5")
        self.app.chap_write_entry.insert(0, "1-3")
        self.app.chap_write_entry.pack(side="left", padx=(0, 12))
        btn_write = ctk.CTkButton(row3, text="✍️ 启动执笔集群", height=34, fg_color="#16A34A", hover_color="#15803D", command=self.app._run_write)
        btn_write.pack(side="left")
        self.app._all_buttons.append(btn_write)

        # ── 工具区 ──
        f4 = self.app._card(scroll, "🔧 工具箱")
        row4 = ctk.CTkFrame(f4, fg_color="transparent")
        row4.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row4, text="卷号:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.app.reindex_vol_entry = ctk.CTkEntry(row4, width=60, height=34)
        self.app.reindex_vol_entry.insert(0, "1")
        self.app.reindex_vol_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row4, text="章节:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.app.reindex_chap_entry = ctk.CTkEntry(row4, width=100, height=34, placeholder_text="如 1-5")
        self.app.reindex_chap_entry.insert(0, "1-5")
        self.app.reindex_chap_entry.pack(side="left", padx=(0, 8))
        btn_reindex = ctk.CTkButton(row4, text="🔄 重建 RAG 记忆", height=34, fg_color="#9333EA", hover_color="#7E22CE", command=self.app._run_reindex)
        btn_reindex.pack(side="left")
        self.app._all_buttons.append(btn_reindex)

    def _build_tab_skills(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # ── 已加载的插件列表 ──
        f_loaded = self.app._card(scroll, "📋 已加载的插件 (Skills)")
        ctk.CTkLabel(f_loaded, text="以下插件已被 PluginManager 自动扫描并挂载到 EventBus:",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(anchor="w", padx=12, pady=(4, 4))
        self.app.skills_list_frame = ctk.CTkFrame(f_loaded, fg_color="transparent")
        self.app.skills_list_frame.pack(fill="x", padx=12, pady=(0, 8))
        self.app._refresh_skills_list()

        btn_row = ctk.CTkFrame(f_loaded, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(btn_row, text="🔄 刷新列表", width=130, height=32, command=self.app._refresh_skills_list).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="♻️ 热重载全部插件", width=160, height=32, fg_color="#9333EA", hover_color="#7E22CE",
                      command=self.app._reload_all_skills).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="📂 打开 skills 目录", width=150, height=32, fg_color="transparent", border_width=2,
                      text_color=("gray10", "#DCE4EE"),
                      command=lambda: os.startfile(os.path.abspath("skills"))).pack(side="left")

        # ── 单个插件热重载 ──
        f_single = self.app._card(scroll, "🔧 单个插件热重载")
        ctk.CTkLabel(f_single, text="输入 skills/ 下的文件夹名进行单插件热更新:",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(anchor="w", padx=12, pady=(4, 2))
        row_single = ctk.CTkFrame(f_single, fg_color="transparent")
        row_single.pack(fill="x", padx=12, pady=(0, 10))
        self.app.single_skill_entry = ctk.CTkEntry(row_single, height=34, placeholder_text="如 core_memory_rag")
        self.app.single_skill_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(row_single, text="♻️ 热重载", height=34, fg_color="#F59E0B", hover_color="#D97706",
                      command=self.app._hot_reload_single_skill).pack(side="right")

        # ── SkillBuilder Agent (Meta-Generation) ──
        f_builder = self.app._card(scroll, "🤖 SkillBuilder Agent (Meta-Generation)")
        ctk.CTkLabel(f_builder, text="用自然语言描述你需要的插件功能，大模型会自动生成合法的 BaseSkill 子类代码并热重载:",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(anchor="w", padx=12, pady=(4, 2))
        self.app.agent_intent_entry = ctk.CTkTextbox(f_builder, height=80, font=ctk.CTkFont(family="Consolas", size=12))
        self.app.agent_intent_entry.pack(fill="x", padx=12, pady=(4, 8))
        self.app.agent_intent_entry.insert("0.0", "帮我写一个 Skill，在每次生成前自动注入一句 '主角很帅' 到 prompt 中")
        agent_btn = ctk.CTkButton(f_builder, text="✨ 召唤 SkillBuilder Agent 生成插件",
                                  command=self.app._run_skill_builder, fg_color="#F59E0B", hover_color="#D97706", height=36)
        agent_btn.pack(anchor="e", padx=12, pady=(0, 10))
        self.app._all_buttons.append(agent_btn)

        # ── 开发指南卡片 ──
        f_guide = self.app._card(scroll, "📚 手动开发指南")
        guide_text = """要手动开发一个 V3 插件 (Skill)，请按以下步骤操作：..."""
        guide_box = ctk.CTkTextbox(f_guide, height=180, font=ctk.CTkFont(family="Consolas", size=11))
        guide_box.pack(fill="x", padx=12, pady=(4, 10))
        guide_box.insert("0.0", guide_text)
        guide_box.configure(state="disabled")

    def _build_tab_config(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        ctk.CTkLabel(scroll, text="当前 env 文件内容（修改请使用左侧面板后点击保存）", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10, pady=(10, 4))

        self.app.env_preview = ctk.CTkTextbox(scroll, font=ctk.CTkFont(family="Consolas", size=12), height=250)
        self.app.env_preview.pack(fill="both", expand=True, padx=10, pady=8)
        self.app._refresh_env_preview()

        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(btn_row, text="🔄 刷新预览", width=140, command=self.app._refresh_env_preview).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="📂 打开 env 文件", width=140, command=lambda: os.startfile(os.path.abspath(ENV_PATH)) if os.path.exists(ENV_PATH) else print("[WARN] env 文件不存在")).pack(side="left")

    def _build_tab_prompts(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        prompts_config = [
            ("s01", "🌍 世界观生成提示词 (world_builder)", "PROMPT_S01_WORLDBUILD", DEFAULT_PROMPT_S01),
            ("s02", "📋 章节打点提示词 (volume_planner)", "PROMPT_S02_BEATS", DEFAULT_PROMPT_S02),
            ("s03w", "✍️ 场景写作提示词 (scene_writer)", "PROMPT_S03_WRITER", DEFAULT_PROMPT_S03_WRITER),
            ("s03e", "🖊️ Editor 润色提示词 (editor)", "PROMPT_S03_EDITOR", DEFAULT_PROMPT_S03_EDITOR),
        ]

        self.app.prompt_boxes = {}
        for key, title, env_key, default in prompts_config:
            f = self.app._card(scroll, title)
            box = ctk.CTkTextbox(f, height=120, font=ctk.CTkFont(family="Consolas", size=12))
            box.pack(fill="x", padx=12, pady=(4, 4))
            box.insert("0.0", os.getenv(env_key, default))
            self.app.prompt_boxes[env_key] = box
            ctk.CTkButton(f, text=f"💾 保存 {key} 提示词", width=160, height=30, command=lambda ek=env_key: self.app._save_single_prompt(ek)).pack(anchor="e", padx=12, pady=(0, 8))

    def _build_tab_batch(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        f1 = self.app._card(scroll, "📦 步骤 1：构建 JSONL 请求文件")
        row1 = ctk.CTkFrame(f1, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row1, text="卷号:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.app.batch_vol_entry = ctk.CTkEntry(row1, width=60, height=34)
        self.app.batch_vol_entry.insert(0, "1")
        self.app.batch_vol_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row1, text="章节范围:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.app.batch_chap_entry = ctk.CTkEntry(row1, width=100, height=34, placeholder_text="1-50")
        self.app.batch_chap_entry.insert(0, "1-50")
        self.app.batch_chap_entry.pack(side="left", padx=(0, 8))
        btn_build = ctk.CTkButton(row1, text="🔨 构建 JSONL", height=34, command=self.app._run_batch_build)
        btn_build.pack(side="left")
        self.app._all_buttons.append(btn_build)

        f2 = self.app._card(scroll, "🚀 步骤 2：提交到云端")
        row2 = ctk.CTkFrame(f2, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row2, text="JSONL 路径:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.app.batch_jsonl_entry = ctk.CTkEntry(row2, height=34, placeholder_text=".novel/batch_jobs/vol_01_ch_1_50_req.jsonl")
        self.app.batch_jsonl_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn_submit = ctk.CTkButton(row2, text="📤 提交任务", height=34, command=self.app._run_batch_submit)
        btn_submit.pack(side="right")
        self.app._all_buttons.append(btn_submit)

        f3 = self.app._card(scroll, "🔄 步骤 3：同步结果")
        row3 = ctk.CTkFrame(f3, fg_color="transparent")
        row3.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row3, text="Batch ID:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 4))
        self.app.batch_id_entry = ctk.CTkEntry(row3, height=34, placeholder_text="batch_xxx")
        self.app.batch_id_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn_sync = ctk.CTkButton(row3, text="⬇️ 同步结果", height=34, fg_color="#16A34A", hover_color="#15803D", command=self.app._run_batch_sync)
        btn_sync.pack(side="right")
        self.app._all_buttons.append(btn_sync)

    def _build_tab_viewer(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        f1 = self.app._card(scroll, "📄 当前文件内容")
        self.app.viewer_path_label = ctk.CTkLabel(f1, text="等待选择文件...", font=ctk.CTkFont(size=12, weight="bold"), text_color="#60A5FA", anchor="w")
        self.app.viewer_path_label.pack(fill="x", padx=12, pady=(8, 4))
        
        self.app.viewer_text_box = ctk.CTkTextbox(f1, font=ctk.CTkFont(family="Consolas", size=13), height=450, wrap="word")
        self.app.viewer_text_box.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.app.viewer_text_box.insert("0.0", "请在左侧文件树中双击文件，或选中后点击底部的【👀 查看所选】。")
        self.app.viewer_text_box.configure(state="disabled")

    def _build_tab_review(self, parent):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        f1 = self.app._card(scroll, "🎯 选定目标文件 (可多选)")
        ctk.CTkLabel(f1, text="你可以从左侧文件树选择多个文件并点击【➕ 加入审阅】：", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=(8, 2))
        
        row1 = ctk.CTkFrame(f1, fg_color="transparent")
        row1.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.app.review_target_list = ctk.CTkTextbox(row1, height=80, font=ctk.CTkFont(family="Consolas", size=12))
        self.app.review_target_list.pack(side="left", fill="both", expand=True)

        btn_clear = ctk.CTkButton(row1, text="🗑️ 清空", width=60, hover_color="#DC2626",
                                  command=lambda: self.app.review_target_list.delete("0.0", "end"))
        btn_clear.pack(side="right", padx=(8, 0), anchor="n")

        f2 = self.app._card(scroll, "📝 修改意见与指令")
        ctk.CTkLabel(f2, text="输入你的审阅意见，AI 将根据该意见修改选中文件：", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=(8, 2))
        self.app.review_instruction_entry = ctk.CTkTextbox(f2, height=150, font=ctk.CTkFont(family="Consolas", size=13))
        self.app.review_instruction_entry.pack(fill="x", padx=12, pady=(0, 10))
        self.app.review_instruction_entry.insert("0.0", "例如：\n请统一以下文件中主角的战力设定。\n或者：根据第一个文件的大纲修改后续文件。")

        btn_review = ctk.CTkButton(scroll, text="✨ 提交 AI 辅助修改 (支持多文件)", height=40, font=ctk.CTkFont(size=14, weight="bold"),
                                   fg_color="#F59E0B", hover_color="#D97706", command=self.app._run_ai_review)
        btn_review.pack(padx=12, pady=(15, 10), fill="x")
        self.app._all_buttons.append(btn_review)
