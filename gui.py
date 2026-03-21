import os
import sys
import queue
import customtkinter as ctk
from dotenv import load_dotenv

# --- 导入模块化组件 ---
from gui_modules.constants import ENV_PATH
from gui_modules.utils import TextRedirector
from gui_modules.ui_helpers import sidebar_section, card
from gui_modules.components.sidebar import SidebarFrame
from gui_modules.components.terminal import TerminalFrame
from gui_modules.components.tabs import MainTabs
import gui_modules.logic as logic

# --- 环境变量加载 ---
load_dotenv(dotenv_path=ENV_PATH)

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

        # 构建组件
        self.sidebar = SidebarFrame(self)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        
        self.tabs = MainTabs(self)
        self.tabs.grid(row=0, column=1, padx=(0, 16), pady=(10, 4), sticky="nsew")
        
        self.terminal = TerminalFrame(self)
        self.terminal.grid(row=1, column=1, padx=(0, 16), pady=(4, 12), sticky="nsew")

        # 终端重定向
        self.log_queue = queue.Queue()
        sys.stdout = TextRedirector(self.log_queue)
        sys.stderr = TextRedirector(self.log_queue)
        
        # 初始化 V3 微内核
        self._init_v3_kernel()

        # 启动日志轮询
        self.after(80, self._poll_log_queue)

        print("═" * 60)
        print("  🚀 Novel-Claude V3 微内核引擎已启动 (Modular Edition)")
        print(f"  📂 当前项目: {os.getenv('NOVEL_NAME', '默认')}")
        print(f"  🤖 当前模型: {os.getenv('MODEL_ID', 'glm-4.6v')}")
        loaded_count = len(self.novel_context.active_skills) if hasattr(self, 'novel_context') else 0
        print(f"  🔌 已加载插件: {loaded_count} 个")
        print("═" * 60)

    # ──────────────────────────────────
    #  UI 辅助方法 (代理)
    # ──────────────────────────────────
    def _sidebar_section(self, parent, title):
        sidebar_section(parent, title)

    def _card(self, parent, title):
        return card(parent, title)

    # ──────────────────────────────────
    #  逻辑方法 (委托)
    # ──────────────────────────────────
    def _poll_log_queue(self):
        logic.poll_log_queue(self)

    def _init_v3_kernel(self):
        logic.init_v3_kernel(self)

    def _save_all_config(self):
        logic.save_all_config(self)

    def _save_single_prompt(self, env_key):
        logic.save_single_prompt(self, env_key)

    def _exec_cmd(self, event=None):
        logic.exec_cmd(self, event)

    def _refresh_skills_list(self):
        logic.refresh_skills_list(self)

    def _reload_all_skills(self):
        logic.reload_all_skills(self)

    def _clear_terminal(self):
        self.console_text.configure(state="normal")
        self.console_text.delete("0.0", "end")
        self.console_text.configure(state="disabled")

    def _refresh_env_preview(self):
        self._show_env_preview()

    def _show_env_preview(self):
        self.env_preview.configure(state="normal")
        self.env_preview.delete("0.0", "end")
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                self.env_preview.insert("0.0", f.read())
        except FileNotFoundError:
            self.env_preview.insert("0.0", "(env 文件不存在)")
        self.env_preview.configure(state="disabled")

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

    def _toggle_skill(self, name, enable):
        print(f"[UI] {'启用' if enable else '禁用'}插件: {name}")
        if enable:
            self.plugin_manager.enable_skill(name)
        else:
            self.plugin_manager.disable_skill(name)
        self._refresh_skills_list()

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

    # ── 工作流按钮回调 委托给 logic ──
    def _run_skill_builder(self):
        logic.run_skill_builder(self)

    def _run_init(self):
        logic.run_init(self)

    def _run_macro_plan(self):
        logic.run_macro_plan(self)

    def _run_vol_plan(self):
        logic.run_vol_plan(self)

    def _run_write(self):
        logic.run_write(self)

    def _run_reindex(self):
        logic.run_reindex(self)

    def _run_batch_build(self):
        logic.run_batch_build(self)

    def _run_batch_submit(self):
        logic.run_batch_submit(self)

    def _run_batch_sync(self):
        logic.run_batch_sync(self)


if __name__ == "__main__":
    app = NovelClaudeGUI()
    app.mainloop()