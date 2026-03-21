import os
import sys
import threading
import importlib
from dotenv import set_key
from .constants import ENV_PATH

def init_v3_kernel(app):
    """挂载 NovelContext 和 PluginManager"""
    from core.novel_context import NovelContext
    from core.plugin_manager import PluginManager
    from utils.workspace import WorkspaceManager
    import utils.config as sys_config
    
    print("[INFO] 正在挂载 V3 微内核...")
    app.workspace_mgr = WorkspaceManager(sys_config.NOVEL_DIR)
    app.novel_context = NovelContext(app.workspace_mgr)
    app.plugin_manager = PluginManager(app.novel_context)
    app.plugin_manager.scan_and_load()
    # 刷新 UI 上的插件列表
    if hasattr(app, 'tabs'):
        refresh_skills_list(app)

def save_all_config(app):
    import utils.config as sys_config
    pairs = {
        "ANTHROPIC_BASE_URL": app.url_entry.get(),
        "ANTHROPIC_API_KEY": app.key_entry.get(),
        "MODEL_ID": app.model_entry.get(),
        "FLASH_MODEL_ID": app.flash_model_entry.get(),
        "NOVEL_NAME": app.novel_name_entry.get().strip(),
        "CHAPTER_TARGET_WORDS": str(int(app.words_slider.get())),
        "TOTAL_VOLUMES": app.total_vols_entry.get().strip(),
        "CHAPTERS_PER_VOLUME": app.chaps_per_vol_entry.get().strip(),
        "CHUNK_SIZE": app.chunk_entry.get().strip(),
        "LLM_PROVIDER": app.provider_var.get(),
    }
    for k, v in pairs.items():
        set_key(ENV_PATH, k, v)
        os.environ[k] = v
        
    importlib.reload(sys_config)
    init_v3_kernel(app)
    
    app._show_env_preview()
    print("[✓] 全部配置已保存并重载 V3 微内核。")

def save_single_prompt(app, env_key):
    box = app.prompt_boxes[env_key]
    text = box.get("0.0", "end").strip()
    set_key(ENV_PATH, env_key, text)
    os.environ[env_key] = text
    print(f"[✓] 提示词 {env_key} 已保存！")

def exec_cmd(app, event=None):
    import subprocess
    cmd = app.cmd_entry.get().strip()
    if not cmd:
        return
    app.cmd_entry.delete(0, "end")
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

def refresh_skills_list(app):
    """刷新已加载插件的列表显示"""
    import customtkinter as ctk
    for widget in app.skills_list_frame.winfo_children():
        widget.destroy()

    skills_dir = "skills"
    all_dirs = []
    if os.path.exists(skills_dir):
        all_dirs = [d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d)) and not d.startswith("__") and not d.startswith(".")]

    active_skills = getattr(app, 'novel_context', None) and app.novel_context.active_skills or {}

    if not all_dirs and not active_skills:
        ctk.CTkLabel(app.skills_list_frame, text="  (暂无发现的插件)",
                     font=ctk.CTkFont(size=11), text_color="gray50").pack(anchor="w")
        if hasattr(app, 'skill_status_label'):
            app.skill_status_label.configure(text="已加载: 0 个插件")
        return

    loaded_count = 0
    for name in all_dirs:
        is_active = name in active_skills
        is_disabled = os.path.exists(os.path.join(skills_dir, name, ".disabled"))
        
        row = ctk.CTkFrame(app.skills_list_frame, fg_color=("gray88", "gray20"), corner_radius=6)
        row.pack(fill="x", pady=2)
        
        if is_disabled:
            ctk.CTkLabel(row, text=f"  🔴 {name}", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray50").pack(side="left", padx=8, pady=6)
            ctk.CTkButton(row, text="启用", width=50, height=26, fg_color="#10B981", hover_color="#059669",
                          command=lambda n=name: app._toggle_skill(n, True)).pack(side="right", padx=6, pady=4)
        elif is_active:
            skill = active_skills[name]
            loaded_count += 1
            ctk.CTkLabel(row, text=f"  🟢 {skill.name}", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=8, pady=6)
            ctk.CTkLabel(row, text=f"({name}/)", font=ctk.CTkFont(size=10), text_color="gray50").pack(side="left")
            ctk.CTkButton(row, text="禁用", width=50, height=26, fg_color="#EF4444", hover_color="#DC2626",
                          command=lambda n=name: app._toggle_skill(n, False)).pack(side="right", padx=6, pady=4)
            ctk.CTkButton(row, text="♻️", width=30, height=26, fg_color="transparent", border_width=1,
                          text_color=("gray10", "#DCE4EE"),
                          command=lambda n=name: app._hot_reload_one(n)).pack(side="right", padx=6, pady=4)
        else:
            ctk.CTkLabel(row, text=f"  ⚠️ {name} (报错)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#F59E0B").pack(side="left", padx=8, pady=6)
            ctk.CTkButton(row, text="禁用", width=50, height=26, fg_color="#EF4444", hover_color="#DC2626",
                          command=lambda n=name: app._toggle_skill(n, False)).pack(side="right", padx=6, pady=4)
            ctk.CTkButton(row, text="♻️", width=30, height=26, fg_color="transparent", border_width=1,
                          text_color=("gray10", "#DCE4EE"),
                          command=lambda n=name: app._hot_reload_one(n)).pack(side="right", padx=6, pady=4)

    if hasattr(app, 'skill_status_label'):
        app.skill_status_label.configure(text=f"已加载: {loaded_count} 个插件")

def reload_all_skills(app):
    print("[INFO] 正在重载全部插件...")
    from core.event_bus import event_bus
    for skill in list(app.novel_context.active_skills.values()):
        event_bus.unregister(skill)
    app.novel_context.active_skills.clear()
    app.plugin_manager.loaded_modules.clear()
    app.plugin_manager.scan_and_load()
    refresh_skills_list(app)
    print("[✓] 全部插件已重载！")

def poll_log_queue(app):
    while not app.log_queue.empty():
        msg = app.log_queue.get()
        app.console_text.configure(state="normal")
        app.console_text.insert("end", msg)
        app.console_text.see("end")
        app.console_text.configure(state="disabled")
    app.after(60, lambda: poll_log_queue(app))

def run_in_thread(app, label, task_func, *args):
    if app._task_running:
        print("[WARN] 有任务正在运行中，请等待完成后再启动新任务。")
        return
    app._task_running = True
    for btn in app._all_buttons:
        btn.configure(state="disabled")
    app.status_label.configure(text=f"⏳ {label} — 运行中...", text_color="#FBBF24")

    def wrapper():
        try:
            from world_builder import run_world_builder
            from volume_planner import run_volume_planner, plan_macro_outlines
            from scene_writer import run_scene_writer
            from utils.config import wait_for_background_tasks
            
            task_func(*args)
            wait_for_background_tasks()
            print(f"\n[🎉] {label} 全部完成！\n")
            app.status_label.configure(text=f"✅ {label} — 已完成", text_color="#34D399")
        except Exception as e:
            print(f"\n[🚨 Error] {label} 失败: {e}\n")
            app.status_label.configure(text=f"❌ {label} — 失败", text_color="#F87171")
        finally:
            app._task_running = False
            for btn in app._all_buttons:
                btn.configure(state="normal")

    threading.Thread(target=wrapper, daemon=True).start()

def run_skill_builder(app):
    intent = app.agent_intent_entry.get("0.0", "end").strip()
    if not intent:
        print("[WARN] 请先输入开发需求！")
        return
        
    def builder_task():
        from core.agents.skill_builder_agent import SkillBuilderAgent
        agent = SkillBuilderAgent(app.novel_context, app.plugin_manager)
        agent.build_skill(intent)
        refresh_skills_list(app)
        
    run_in_thread(app, "Meta-Generation", builder_task)

def run_init(app):
    logline = app.logline_entry.get().strip()
    if not logline:
        print("[WARN] 请先输入核心创意！")
        return
    from world_builder import run_world_builder
    run_in_thread(app, "世界观初始化", run_world_builder, logline)

def run_macro_plan(app):
    from volume_planner import plan_macro_outlines
    run_in_thread(app, "宏观大纲生成", plan_macro_outlines)

def run_vol_plan(app):
    vol = app.vol_plan_entry.get().strip()
    if not vol.isdigit():
        print("[WARN] 目标卷号必须是整数！")
        return
    from volume_planner import run_volume_planner
    run_in_thread(app, f"卷 {vol} 章节细纲生成", run_volume_planner, int(vol))

def run_write(app):
    vol = app.vol_write_entry.get().strip()
    chaps = app.chap_write_entry.get().strip()
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
    from scene_writer import run_scene_writer
    run_in_thread(app, f"卷 {vol} 第 {chaps} 章写作", run_scene_writer, int(vol), start, end)

def run_reindex(app):
    vol = app.reindex_vol_entry.get().strip()
    chaps = app.reindex_chap_entry.get().strip()
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

    run_in_thread(app, f"RAG 记忆重建 (卷{vol} 章{chaps})", reindex_task)

def run_batch_build(app):
    vol = app.batch_vol_entry.get().strip()
    chaps = app.batch_chap_entry.get().strip()
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
        app.batch_jsonl_entry.delete(0, "end")
        app.batch_jsonl_entry.insert(0, output_path)

    run_in_thread(app, "构建 Batch JSONL", build_task)

def run_batch_submit(app):
    jsonl_path = app.batch_jsonl_entry.get().strip()
    if not jsonl_path or not os.path.exists(jsonl_path):
        print(f"[WARN] 找不到文件: {jsonl_path}")
        return

    def submit_task():
        from utils.batch_client import submit_batch_task
        batch_id = submit_batch_task(jsonl_path, desc=f"Submit: {os.path.basename(jsonl_path)}")
        print(f"\n[✓] Batch ID: {batch_id}")
        app.batch_id_entry.delete(0, "end")
        app.batch_id_entry.insert(0, batch_id)

    run_in_thread(app, "提交 Batch 任务", submit_task)

def run_batch_sync(app):
    batch_id = app.batch_id_entry.get().strip()
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

    run_in_thread(app, "Batch 同步", sync_task)
