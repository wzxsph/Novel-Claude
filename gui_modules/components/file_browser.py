import os
import customtkinter as ctk
import tkinter.ttk as ttk

class FileBrowserFrame(ctk.CTkFrame):
    def __init__(self, master, on_view_file=None, on_add_review=None, **kwargs):
        super().__init__(master, corner_radius=0, **kwargs)
        self.app = master
        self.on_view_file = on_view_file
        self.on_add_review = on_add_review
        self.current_root = os.getcwd()

        self._build_ui()
        self.refresh_tree()

    def _build_ui(self):
        # 顶栏
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=10, pady=(15, 5))
        
        ctk.CTkLabel(top_frame, text="📂 Workspace", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        
        btn_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        btn_frame.pack(side="right")
        
        ctk.CTkButton(btn_frame, text="🔄", width=30, height=26, fg_color="transparent", border_width=1,
                      text_color=("gray10", "#DCE4EE"), command=self.refresh_tree).pack(side="right", padx=(4, 0))
        ctk.CTkButton(btn_frame, text="🔙", width=30, height=26, fg_color="transparent", border_width=1,
                      text_color=("gray10", "#DCE4EE"), command=self.go_up).pack(side="right")

        # 当前路径提示
        self.path_label = ctk.CTkLabel(self, text=self.current_root, font=ctk.CTkFont(size=11), text_color="gray50", anchor="w")
        self.path_label.pack(fill="x", padx=10, pady=(0, 10))

        # 配置 Treeview 样式 (匹配 Dark 主题)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except:
            pass
        style.configure("Treeview", 
                        background="#2b2b2b",
                        foreground="white",
                        fieldbackground="#2b2b2b",
                        borderwidth=0,
                        font=("Consolas", 13), # 更大的字体
                        rowheight=28)          # 更大的行高
        style.map("Treeview", background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="white", borderwidth=0, font=("Consolas", 13, "bold"))

        # Treeview 及其滚动条
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)
        
        self.tree = ttk.Treeview(tree_frame, selectmode="extended", show="tree")
        self.tree.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # 绑定双击事件 (默认用作在查看器打开)
        self.tree.bind("<Double-1>", self._on_double_click)

        # 底部操作按钮
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", side="bottom", padx=10, pady=(4, 10))
        
        btn_view = ctk.CTkButton(bottom_frame, text="👀 查看所选", height=32, command=self._on_btn_view)
        btn_view.pack(side="left", fill="x", expand=True, padx=(0, 4))
        
        btn_review = ctk.CTkButton(bottom_frame, text="➕ 加入审阅", height=32, fg_color="#F59E0B", hover_color="#D97706", command=self._on_btn_review)
        btn_review.pack(side="left", fill="x", expand=True, padx=(4, 0))

    def refresh_tree(self):
        """扫描当前根目录并填充 Treeview"""
        self.path_label.configure(text=self.current_root)
        
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            # 获取 .novel 目录优先 (如果存在)
            novel_name = os.getenv("NOVEL_NAME", "").strip()
            target_dir = os.path.join(self.current_root, ".novel")
            if novel_name:
                target_dir = os.path.join(self.current_root, ".novel", novel_name)
                
            if os.path.exists(target_dir):
                self._insert_node("", target_dir, "(Project Root) " + os.path.basename(target_dir))
            
            # 同时也显示当前目录下的其他文件
            self._populate_dir("", self.current_root)
        except Exception as e:
            print(f"[FileBrowser] 刷新目录失败: {e}")

    def _populate_dir(self, parent, path):
        try:
            dirs = []
            files = []
            for item in os.listdir(path):
                if item.startswith("__") or item == ".git" or item == ".novel":
                    continue
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    dirs.append((item, full_path))
                else:
                    files.append((item, full_path))
                    
            dirs.sort(key=lambda x: x[0].lower())
            files.sort(key=lambda x: x[0].lower())

            for d_name, d_path in dirs:
                self._insert_node(parent, d_path, "📁 " + d_name)
            for f_name, f_path in files:
                self._insert_node(parent, f_path, "📄 " + f_name)
        except Exception:
            pass

    def _insert_node(self, parent, path, text):
        is_dir = os.path.isdir(path)
        oid = self.tree.insert(parent, "end", text=text, open=False, values=[path, is_dir])
        if is_dir:
            # 插入一个 dummy 子节点以显示展开箭头
            self.tree.insert(oid, "end", text="dummy")
            # 绑定展开事件以进行懒加载
            self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)

    def _on_tree_open(self, event):
        item_id = self.tree.focus()
        children = self.tree.get_children(item_id)
        if len(children) == 1 and self.tree.item(children[0], "text") == "dummy":
            self.tree.delete(children[0])
            path = self.tree.item(item_id, "values")[0]
            self._populate_dir(item_id, path)

    def _get_selected_files(self):
        """获取所有选中的文件路径（目录会被过滤）"""
        selected_ids = self.tree.selection()
        filepaths = []
        for item_id in selected_ids:
            values = self.tree.item(item_id, "values")
            if values:
                path, is_dir = values[0], values[1]
                if str(is_dir) != 'True':
                    filepaths.append(path)
        return filepaths

    def _on_btn_view(self):
        files = self._get_selected_files()
        if files and self.on_view_file:
            # 查看器通常一次看一个文件，取第一个
            self.on_view_file(files[0])

    def _on_btn_review(self):
        files = self._get_selected_files()
        if files and self.on_add_review:
            # 加入审阅支持多文件
            self.on_add_review(files)

    def _on_double_click(self, event):
        item_id = self.tree.focus()
        if not item_id:
            return
            
        values = self.tree.item(item_id, "values")
        if not values:
            return
            
        path, is_dir = values[0], values[1]
        
        is_dir_bool = str(is_dir) == 'True'
        
        if not is_dir_bool and self.on_view_file:
            self.on_view_file(path)
            
    def go_up(self):
        parent_dir = os.path.dirname(self.current_root)
        if parent_dir != self.current_root:
            self.current_root = parent_dir
            self.refresh_tree()
