import click
from s01_world_builder import run_world_builder
from s02_volume_planner import run_volume_planner, plan_macro_outlines
from s03_scene_writer import run_scene_writer
from utils.config import wait_for_background_tasks

@click.group()
def cli():
    """网文版简易 Claude Code 小说生成系统 (novel-cli)"""
    pass

@cli.command()
@click.argument('logline')
def init(logline):
    """阶段1：初始化世界观（基于一句核心创意）"""
    run_world_builder(logline)
    wait_for_background_tasks()

@cli.command()
@click.option('--volume', type=int, default=None, help='指定的卷号，如果为空则仅生成宏观大纲')
def plan(volume):
    """阶段2：生成大纲与指定卷微观细纲"""
    if volume is None:
        plan_macro_outlines()
    else:
        run_volume_planner(volume)
    wait_for_background_tasks()

@cli.command()
@click.option('--volume', type=int, required=True, help='目标卷号')
@click.option('--chapters', type=str, required=True, help='要生成的章节范围格式如 1-5 或单章 1')
def write(volume, chapters):
    """阶段3：启动场景集群并发/串行写作，以及动态记忆更新"""
    if '-' in chapters:
        start, end = map(int, chapters.split('-'))
    else:
        start = end = int(chapters)
        
    run_scene_writer(volume, start, end)
    
    # User architecture feedback:
    # Ensure memory embedding threads complete successfully without being terminated brutally
    wait_for_background_tasks()

@cli.command()
@click.option('--volume', type=int, required=True, help='目标卷号')
@click.option('--chapters', type=str, required=True, help='要重新补齐记忆的章节范围 (如 1-5)')
def reindex(volume, chapters):
    """【补救措施】手动将已生成的成稿重新导入向量记忆库"""
    from s03_scene_writer import run_scene_writer
    from s04_memory_rag import post_generation_hook
    from utils.config import MANUSCRIPTS_DIR
    import os
    
    if '-' in chapters:
        start, end = map(int, chapters.split('-'))
    else:
        start = end = int(chapters)
        
    for chap in range(start, end + 1):
        path = os.path.join(MANUSCRIPTS_DIR, f"vol_{volume:02d}", f"ch_{chap:03d}_final.md")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                print(f"[REINDEX] 正在补全第 {chap} 章的记忆...")
                post_generation_hook(chap, content)
        else:
            print(f"[WARN] 找不到成稿文件: {path}")
            
    wait_for_background_tasks()

if __name__ == '__main__':
    try:
        cli()
    except KeyboardInterrupt:
        print("\n[WARN] 收到终端停止信号。正在尝试保存并退出后台任务...")
        wait_for_background_tasks()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[ERROR] 执行失败: {e}")
        wait_for_background_tasks()
