import customtkinter as ctk

class TerminalFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=10, **kwargs)
        self.app = master
        self._build_terminal()

    def _build_terminal(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 顶栏
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        ctk.CTkLabel(top, text="💻 系统控制台", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(top, text="🗑️ 清屏", width=70, height=28, fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE"), command=self.app._clear_terminal).pack(side="right")

        # 输出区
        self.app.console_text = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12), wrap="word", state="disabled")
        self.app.console_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(2, 4))

        # 命令输入行
        cmd_frame = ctk.CTkFrame(self, fg_color="transparent")
        cmd_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
        cmd_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(cmd_frame, text="❯", font=ctk.CTkFont(family="Consolas", size=14, weight="bold"), text_color="#60A5FA").grid(row=0, column=0, padx=(0, 6))
        self.app.cmd_entry = ctk.CTkEntry(cmd_frame, font=ctk.CTkFont(family="Consolas", size=12), height=32, placeholder_text="输入 CLI 命令，如：uv run python cli.py plan --volume 1")
        self.app.cmd_entry.grid(row=0, column=1, sticky="ew")
        self.app.cmd_entry.bind("<Return>", self.app._exec_cmd)
        ctk.CTkButton(cmd_frame, text="执行", width=60, height=32, command=self.app._exec_cmd).grid(row=0, column=2, padx=(6, 0))
