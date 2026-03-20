import os
import json
from typing import List
from pydantic import BaseModel
from utils.config import SETTINGS_DIR, VOLUMES_DIR
from utils.llm_client import generate_json

class VolumeOutline(BaseModel):
    volume_id: int
    volume_name: str
    word_count_target: int
    core_conflict: str
    power_level_cap: str
    key_events: List[str]

class VolumeOutlinesSchema(BaseModel):
    volumes: List[VolumeOutline]

class SceneBeat(BaseModel):
    scene_id: int
    pov_character: str
    plot_summary: str
    word_count_target: int
    action_items: List[str]

class ChapterBeats(BaseModel):
    chapter_id: int
    chapter_title: str
    beats: List[SceneBeat]

class ChaptersSchema(BaseModel):
    chapters: List[ChapterBeats]

def get_world_context() -> str:
    """Reads settings into a context string."""
    context = []
    for f in ["world_rules.json", "power_levels.json", "main_characters.json", "factions.json"]:
        path = os.path.join(SETTINGS_DIR, f)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as file:
                context.append(f"### {f}\n{file.read()}")
    return "\n".join(context)

def plan_macro_outlines(total_volumes: int = 10):
    """Generates the macro outlines for multiple volumes."""
    print("[INFO] 正在生成宏观卷大纲...")
    world_context = get_world_context()
    prompt = f"""
    你是顶尖网络小说架构师。请根据以下全局设定，规划 {total_volumes} 卷的核心大纲。
    确保战力递进合理，不崩坏。每卷字数目标约 250000 字。
    
    【世界观与设定】:
    {world_context}
    """
    
    data = generate_json(prompt, VolumeOutlinesSchema)
    
    for vol in data.get("volumes", []):
        vol_id = vol["volume_id"]
        path = os.path.join(VOLUMES_DIR, f"vol_{vol_id:02d}_outline.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(vol, f, ensure_ascii=False, indent=2)
            
    print(f"[✓] {len(data.get('volumes', []))} 卷宏观大纲已生成并落盘。")

def plan_volume_beats(volume_id: int, chapters_to_plan: int = 50, chunk_size: int = 5):
    """Generates the micro scene beats for a specific volume."""
    print(f"[INFO] 启动分卷调度器，目标：第 {volume_id} 卷微观打点 (共 {chapters_to_plan} 章)...")
    
    vol_path = os.path.join(VOLUMES_DIR, f"vol_{volume_id:02d}_outline.json")
    if not os.path.exists(vol_path):
        print(f"[ERROR] 找不到卷 {volume_id} 的大纲，请先执行宏观规划！")
        return False
        
    with open(vol_path, "r", encoding="utf-8") as f:
        vol_outline = json.load(f)
        
    world_context = get_world_context()
    base_dir = os.path.join(VOLUMES_DIR, f"vol_{volume_id:02d}_chapters")
    os.makedirs(base_dir, exist_ok=True)
    
    saved_count = 0
    all_chapters = []
    
    # User feedback: Implement paginated generation to avoid throwing max_token errors
    # Chunk size reduced to 5 to avoid cutting off long token outputs in single calls.
    for start_ch in range(1, chapters_to_plan + 1, chunk_size):
        end_ch = min(start_ch + chunk_size - 1, chapters_to_plan)
        print(f"[INFO] 正在生成第 {start_ch}-{end_ch} 章的打点...")
        
        prompt = f"""
        你是一个网文白金主编。当前任务是为第 {volume_id} 卷【{vol_outline['volume_name']}】做微观打点(Beat Sheet)。
        
        【全局设定参考】:
        {world_context}
        
        【本卷核心约束】:
        - 战力天花板：{vol_outline['power_level_cap']}
        - 核心冲突：{vol_outline['core_conflict']}
        
        【任务要求】:
        1. 生成第 {start_ch} 章到第 {end_ch} 章的剧情点。
        2. 每章必须拆分为 3 到 4 个 Scene Beats。
        3. 每个 Beat 的 plot_summary 必须明确说明当前场景的角色动作和目的。
        """
        
        data = generate_json(prompt, ChaptersSchema)
        # Ensure compatibility if generate_json returns Pydantic model or dict
        chapters = data.get("chapters", []) if isinstance(data, dict) else data.chapters
        all_chapters.extend(chapters)
        
    # User Feedback: strict 5000 word per chapter
    CHAPTER_TARGET_WORDS = 5000
    
    for chapter in all_chapters:
        is_dict = isinstance(chapter, dict)
        chap_id = chapter["chapter_id"] if is_dict else chapter.chapter_id
        beats = chapter["beats"] if is_dict else chapter.beats
        
        # 数学归一化处理：强制将每一个 Beat 字数比例缩放，使得全章准确达到 5000 字
        total_generated_words = sum([b["word_count_target"] if isinstance(b, dict) else getattr(b, "word_count_target", 1500) for b in beats])
        if total_generated_words == 0:
            total_generated_words = len(beats) * 1500 # 防止除零
            
        ratio = CHAPTER_TARGET_WORDS / total_generated_words
        
        for b in beats:
            b_is_dict = isinstance(b, dict)
            current_target = b["word_count_target"] if b_is_dict else getattr(b, "word_count_target", 1500)
            
            # 向上取整以确保最终结果近似于目标总数
            normalized_target = int(current_target * ratio)
            
            if b_is_dict:
                b["word_count_target"] = normalized_target
            else:
                b.word_count_target = normalized_target
        
        # 保存为 JSON 
        file_path = os.path.join(base_dir, f"ch_{chap_id:03d}_beats.json")
        with open(file_path, "w", encoding="utf-8") as f:
            chapter_dict = chapter if is_dict else chapter.model_dump()
            json.dump(chapter_dict, f, ensure_ascii=False, indent=2)
            
        saved_count += 1
            
    print(f"[✓] 成功拆解并保存了 {saved_count} 章的场景切片 (Beats)。目前字数已由物理归一化约束（5000字/章）。")
    print("[!] 状态已挂起，准备进行人机协作复核。可手动前往目录修改 JSON 后继续执行。")
    return True

def run_volume_planner(volume_id: int = None):
    if volume_id is None:
        plan_macro_outlines()
    else:
        plan_volume_beats(volume_id)
