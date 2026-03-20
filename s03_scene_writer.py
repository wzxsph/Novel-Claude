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

# --- Batch Mode Extensions ---

def generate_batch_jsonl(volume_id: int, start_chap: int, end_chap: int, output_jsonl: str):
    """将多个章节的 Beats 转换为 Batch API 所需的 JSONL 格式"""
    requests = []
    world_context = get_world_context()
    
    for chapter_id in range(start_chap, end_chap + 1):
        beats_path = os.path.join(VOLUMES_DIR, f"vol_{volume_id:02d}_chapters", f"ch_{chapter_id:03d}_beats.json")
        if not os.path.exists(beats_path):
            continue
            
        with open(beats_path, "r", encoding="utf-8") as f:
            beat_sheet = json.load(f)
            
        for beat in beat_sheet["beats"]:
            scene_id = beat['scene_id']
            # custom_id 格式: v01_ch001_sc001
            custom_id = f"v{volume_id:02d}_ch{chapter_id:03d}_sc{scene_id:03d}"
            
            # 获取 RAG 记忆注入
            rag_context = pre_generation_hook(beat)
            
            prompt = f"""
            【全局核心设定】：\n{world_context}\n
            {rag_context}
            【当前场景任务】：
            - 视角人物：{beat.get('pov_character', '未知')}
            - 剧情概要：{beat['plot_summary']}
            - 描写重点：{', '.join(beat.get('action_items', []))}
            - 目标字数：约 {beat['word_count_target']} 字
            
            请严格按照小说正文格式展开这段剧情。直接输出正文，不要带有分析、总结等任何多余的废话。
            """
            
            request_obj = {
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v4/chat/completions",
                "body": {
                    "model": "glm-4", # Batch API 建议使用标准模型
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.85
                }
            }
            requests.append(request_obj)
            
    with open(output_jsonl, "w", encoding="utf-8") as f:
        for req in requests:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")
            
    print(f"[✓] 已生成包含 {len(requests)} 个请求的 Batch 文件: {output_jsonl}")

def process_batch_results(result_jsonl: str):
    """解析 Batch 结果并组装成最终章节"""
    scenes_map = {} # { "v01_ch001": { 1: "content" } }
    
    if not os.path.exists(result_jsonl):
        print(f"[ERROR] 找不到结果文件: {result_jsonl}")
        return
        
    with open(result_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            custom_id = data["custom_id"]
            # 解析响应内容
            try:
                content = data["response"]["body"]["choices"][0]["message"]["content"]
            except (KeyError, TypeError):
                print(f"[WARN] 场景 {custom_id} 生成失败或被过滤")
                content = "（该段场景生成失败）"
                
            # 解析 custom_id: v01_ch001_sc001
            parts = custom_id.split("_")
            vol_key = parts[0] # v01
            ch_key = parts[1]  # ch001
            sc_id = int(parts[2][2:]) # sc001 -> 1
            
            key = f"{vol_key}_{ch_key}"
            if key not in scenes_map:
                scenes_map[key] = {}
            scenes_map[key][sc_id] = content

    print(f"[INFO] 正在重组 {len(scenes_map)} 个章节...")
    
    for key, scenes in scenes_map.items():
        # 获取卷号和章号
        vol_id = int(key.split("_")[0][1:])
        ch_id = int(key.split("_")[1][2:])
        
        # 按 scene_id 排序合并
        sorted_scenes = [scenes[k] for k in sorted(scenes.keys())]
        
        # 调用 Director 进行合并润色
        final_content = merge_and_edit_chapter(ch_id, sorted_scenes)
        
        # 保存
        save_dir = os.path.join(MANUSCRIPTS_DIR, f"vol_{vol_id:02d}")
        os.makedirs(save_dir, exist_ok=True)
        final_path = os.path.join(save_dir, f"ch_{ch_id:03d}_final.md")
        with open(final_path, "w", encoding="utf-8") as f:
            f.write(final_content)
            
        print(f"[✓] 第 {ch_id} 章成稿已完成并保存。")
        # 并发触发向量化入库
        post_generation_hook(ch_id, final_content)
