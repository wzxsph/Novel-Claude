import os
import customtkinter as ctk
from .constants import ENV_PATH
from ..ui_helpers import sidebar_section

class SidebarFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, width=280, corner_radius=0, **kwargs)
        self.app = master
        self._build_sidebar()

    def _build_sidebar(self):
        # Logo
        ctk.CTkLabel(self, text="📖 Novel-Claude", font=ctk.CTkFont(size=22, weight="bold")).pack(padx=20, pady=(18, 4))
        ctk.CTkLabel(self, text="V3 微内核 · 插件生态引擎", font=ctk.CTkFont(size=11), text_color="gray60").pack(padx=20, pady=(0, 12))

        # ── API 配置 ──
        sidebar_section(self, "🔗 API 配置")

        ctk.CTkLabel(self, text="Provider:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.app.provider_var = ctk.StringVar(value=os.getenv("LLM_PROVIDER", "zhipu"))
        self.app.provider_menu = ctk.CTkOptionMenu(self, variable=self.app.provider_var, values=["zhipu", "ollama", "custom"], command=self.app._on_provider_change, width=240)
        self.app.provider_menu.pack(padx=20, pady=(2, 8))

        ctk.CTkLabel(self, text="Base URL:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.app.url_entry = ctk.CTkEntry(self, width=240)
        self.app.url_entry.pack(padx=20, pady=(2, 8))
        self.app.url_entry.insert(0, os.getenv("ANTHROPIC_BASE_URL", "https://open.bigmodel.cn/api/anthropic"))

        ctk.CTkLabel(self, text="API Key:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.app.key_entry = ctk.CTkEntry(self, width=240, show="•")
        self.app.key_entry.pack(padx=20, pady=(2, 8))
        self.app.key_entry.insert(0, os.getenv("ANTHROPIC_API_KEY", ""))

        ctk.CTkLabel(self, text="主模型 ID:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.app.model_entry = ctk.CTkEntry(self, width=240)
        self.app.model_entry.pack(padx=20, pady=(2, 8))
        self.app.model_entry.insert(0, os.getenv("MODEL_ID", "glm-4.6v"))

        ctk.CTkLabel(self, text="Flash 模型 ID:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.app.flash_model_entry = ctk.CTkEntry(self, width=240)
        self.app.flash_model_entry.pack(padx=20, pady=(2, 8))
        self.app.flash_model_entry.insert(0, os.getenv("FLASH_MODEL_ID", "glm-4.6v"))

        # ── 生成参数 ──
        self.app._sidebar_section(self, "⚙️ 生成参数")

        ctk.CTkLabel(self, text="项目名称 (NOVEL_NAME):", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.app.novel_name_entry = ctk.CTkEntry(self, width=240, placeholder_text="留空则使用默认 .novel 目录")
        self.app.novel_name_entry.pack(padx=20, pady=(2, 8))
        self.app.novel_name_entry.insert(0, os.getenv("NOVEL_NAME", ""))

        ctk.CTkLabel(self, text=f"每章目标字数: {os.getenv('CHAPTER_TARGET_WORDS', '5000')}", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        self.app.words_slider = ctk.CTkSlider(self, from_=2000, to=10000, number_of_steps=16, width=240, command=self.app._on_words_slider)
        self.app.words_slider.pack(padx=20, pady=(2, 4))
        self.app.words_slider.set(int(os.getenv("CHAPTER_TARGET_WORDS", "5000")))
        self.app.words_label = self.winfo_children()[-2]

        row_frame = ctk.CTkFrame(self, fg_color="transparent")
        row_frame.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_frame, text="总卷数:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.app.total_vols_entry = ctk.CTkEntry(row_frame, width=60)
        self.app.total_vols_entry.pack(side="left", padx=(4, 16))
        self.app.total_vols_entry.insert(0, os.getenv("TOTAL_VOLUMES", "10"))
        ctk.CTkLabel(row_frame, text="每卷章数:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.app.chaps_per_vol_entry = ctk.CTkEntry(row_frame, width=60)
        self.app.chaps_per_vol_entry.pack(side="left", padx=4)
        self.app.chaps_per_vol_entry.insert(0, os.getenv("CHAPTERS_PER_VOLUME", "50"))

        row_frame2 = ctk.CTkFrame(self, fg_color="transparent")
        row_frame2.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_frame2, text="Chunk Size:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.app.chunk_entry = ctk.CTkEntry(row_frame2, width=60)
        self.app.chunk_entry.pack(side="left", padx=4)
        self.app.chunk_entry.insert(0, os.getenv("CHUNK_SIZE", "5"))

        # ── 按钮区 ──
        self.app._sidebar_section(self, "")
        save_btn = ctk.CTkButton(self, text="💾 保存全部配置", command=self.app._save_all_config, fg_color="#2563EB", hover_color="#1D4ED8", height=36)
        save_btn.pack(padx=20, pady=(0, 10), fill="x")

        # ── 插件快捷入口 ──
        self.app._sidebar_section(self, "🔌 插件快捷")
        self.app.skill_status_label = ctk.CTkLabel(self, text="已加载: 0 个插件", font=ctk.CTkFont(size=11), text_color="#60A5FA")
        self.app.skill_status_label.pack(anchor="w", padx=20, pady=(0, 4))
        reload_btn = ctk.CTkButton(self, text="🔄 重载全部插件", command=self.app._reload_all_skills, fg_color="#9333EA", hover_color="#7E22CE", height=32)
        reload_btn.pack(padx=20, pady=(0, 4), fill="x")

        # 主题切换
        theme_frame = ctk.CTkFrame(self, fg_color="transparent")
        theme_frame.pack(fill="x", padx=20, pady=(10, 14))
        ctk.CTkLabel(theme_frame, text="🌙 主题:", font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkOptionMenu(theme_frame, values=["Dark", "Light", "System"], command=lambda v: ctk.set_appearance_mode(v), width=100).pack(side="right")
