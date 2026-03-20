import os
import json
from utils.config import VOLUMES_DIR, MANUSCRIPTS_DIR
from utils.llm_client import generate_stream
from s04_memory_rag import pre_generation_hook, post_generation_hook
from s02_volume_planner import get_world_context

def spawn_writer_subagent(previous_text: str, beat_data: dict, global_context: str) -> str:
    """
    无死角语境隔离的 Subagent。负责单一切片的专注生成。
    """
    print(f"\n[Subagent] 正在生成场景 {beat_data['scene_id']} ... (目标字数: {beat_data['word_count_target']})")
    
    # 抽取并检索相关实体最新状态
    rag_context = pre_generation_hook(beat_data)
    
    prompt = f"""
    【全局核心设定】：\n{global_context}\n
    {rag_context}
    【前情回顾】：\n{previous_text[-500:] if previous_text else "（本章开篇）"}\n
    【当前场景任务】：
    - 视角人物：{beat_data.get('pov_character', '未知')}
    - 剧情概要：{beat_data['plot_summary']}
    - 描写重点：{', '.join(beat_data.get('action_items', []))}
    - 目标字数：约 {beat_data['word_count_target']} 字
    
    请严格按照小说正文格式展开这段剧情。直接输出正文，不要带有分析、总结等任何多余的废话。
    """
    
    scene_content = generate_stream(prompt)
    return scene_content

def merge_and_edit_chapter(chapter_id: int, scenes_content: list) -> str:
    """
    Director Agent 专属合并逻辑。
    """
    print(f"\n\n[Director] 正在拼接并润色第 {chapter_id} 章...")
    raw_text = "\n\n***\n\n".join(scenes_content)
    
    edit_prompt = f"""
    请将以下零散的场景拼接成一章连贯的网文。
    任务：
    1. 抹除 "***" 分割线，替换为平滑的自然段过渡。
    2. 检查逻辑连贯性，保持强烈的断章悬念感。
    3. 直接输出小说的正文内容，绝不要输出分析、多余的标记。
    \n\n{raw_text}
    """
    
    final_chapter = generate_stream(edit_prompt, system_message="你是顶尖网文白金编辑，专门做段落润色和节奏把控。")
    return final_chapter

def run_scene_writer(volume_id: int, start_chapter: int, end_chapter: int):
    world_context = get_world_context()
    
    for chapter_id in range(start_chapter, end_chapter + 1):
        beats_path = os.path.join(VOLUMES_DIR, f"vol_{volume_id:02d}_chapters", f"ch_{chapter_id:03d}_beats.json")
        if not os.path.exists(beats_path):
            print(f"[ERROR] 找不到卷 {volume_id} 章 {chapter_id} 的 Beat 数据，请确认分卷打点已完成。")
            continue
            
        with open(beats_path, "r", encoding="utf-8") as f:
            beat_sheet = json.load(f)
            
        print(f"\n============================================\n[INFO] 启动场景子智能体集群，目标：卷 {volume_id} 章 {chapter_id} : {beat_sheet.get('chapter_title', '')}\n============================================")
        
        chapter_scenes = []
        previous_text = ""
        
        # Serialize the agents generation
        for beat in beat_sheet["beats"]:
            scene_text = spawn_writer_subagent(previous_text, beat, world_context)
            chapter_scenes.append(scene_text)
            # Update previous_text for the upcoming Subagent
            previous_text = scene_text
            
        # Call merger
        final_content = merge_and_edit_chapter(chapter_id, chapter_scenes)
        
        # Save manuscript
        save_dir = os.path.join(MANUSCRIPTS_DIR, f"vol_{volume_id:02d}")
        os.makedirs(save_dir, exist_ok=True)
        final_path = os.path.join(save_dir, f"ch_{chapter_id:03d}_final.md")
        with open(final_path, "w", encoding="utf-8") as f:
            f.write(final_content)
            
        print(f"\n[✓] 第 {chapter_id} 章成稿已保存至 {final_path}")
        
        # Async invoke background thread for RAG
        post_generation_hook(chapter_id, final_content)
