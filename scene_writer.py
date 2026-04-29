"""
Scene Writer - Chapter content generation with @DSL context injection

Following NovelForge's approach:
1. Generate chapter content from chapter_outline (not beats directly)
2. Use @DSL to inject: world_setting, organization cards, scene cards,
   character cards, previous chapter content, writing guide
3. Add continuation support with word count control
4. Progressive saving and state machine management
"""

import os
import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from utils.config import SETTINGS_DIR, VOLUMES_DIR, MANUSCRIPTS_DIR
from utils.config_loader import get_config
from utils.llm_client import ProgressiveWriter, generate_stream
from core.context_assembler import assemble_context, get_assembler
from core.event_bus import event_bus
from utils.chapter_state import get_state_manager, STATE_PENDING, STATE_GENERATING, STATE_COMPLETED, STATE_FAILED


# ============================================================================
# Core Functions
# ============================================================================

def load_chapter_outline(volume_id: int, chapter_id: int) -> Optional[dict]:
    """Load chapter outline from vol_NN_chapters/ch_XXX_outline.json"""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_chapters" / f"ch_{chapter_id:03d}_outline.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_volume_outline(volume_id: int) -> Optional[dict]:
    """Load volume outline from volumes/vol_XX_outline.json"""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_outline.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_previous_chapter(volume_id: int, chapter_id: int) -> Optional[str]:
    """Load previous chapter content for context."""
    if chapter_id <= 1:
        return None
    prev_chars = get_config("writing.previous_chapter_chars", 2000)
    path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id-1:03d}_final.md"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            return content[-prev_chars:]
    return None


def load_history_chapters(volume_id: int, chapter_id: int, count: int = None) -> str:
    """Load multiple previous chapters for deeper context."""
    if count is None:
        count = get_config("writing.history_chapters_count", 3)

    if chapter_id <= count:
        count = chapter_id - 1
    if count <= 0:
        return ""

    history = []
    for i in range(1, count + 1):
        prev_id = chapter_id - i
        if prev_id < 1:
            break
        path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{prev_id:03d}_final.md"
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                # Get key plot points from each chapter (first 200 and last 500 chars)
                content = f.read()
                first_part = content[:200] if len(content) > 200 else content
                last_part = content[-500:] if len(content) > 500 else content
                history.append(f"=== 第{prev_id}章梗概 ===\n{first_part}\n...（中间内容）...\n{last_part}")

    return "\n\n".join(history)


def load_next_chapter_outline(volume_id: int, chapter_id: int) -> Optional[dict]:
    """Load next chapter outline for continuity check."""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_chapters" / f"ch_{chapter_id+1:03d}_outline.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_entity_cards(entity_names: List[str]) -> Dict[str, List[dict]]:
    """Load entity cards (character, scene, organization) matching the given names."""
    result = {
        "characters": [],
        "scenes": [],
        "organizations": []
    }

    blueprint_path = Path(SETTINGS_DIR) / "core_blueprint.json"
    if not blueprint_path.exists():
        return result

    with open(blueprint_path, 'r', encoding='utf-8') as f:
        blueprint = json.load(f)

    content = blueprint.get("content", blueprint)
    entity_name_set = set(entity_names)

    # Filter characters
    for char in content.get("character_cards", []):
        if char.get("name") in entity_name_set:
            result["characters"].append(char)

    # Filter scenes
    for scene in content.get("scene_cards", []):
        if scene.get("name") in entity_name_set:
            result["scenes"].append(scene)

    # Filter organizations
    for org in content.get("organization_cards", []):
        if org.get("name") in entity_name_set:
            result["organizations"].append(org)

    return result


def load_world_setting() -> dict:
    """Load world setting for context."""
    path = Path(SETTINGS_DIR) / "world_setting.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def load_writing_guide(volume_id: int) -> Optional[str]:
    """Load writing guide for the volume if exists."""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_writing_guide.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("content", {}).get("content", "")
    return None


def generate_chapter_content(volume_id: int, chapter_id: int, state_manager=None) -> str:
    """
    Generate chapter content from chapter outline using @DSL context injection.
    Supports progressive saving via state_manager.
    """
    print(f"\n[INFO] 正在生成第 {volume_id} 卷第 {chapter_id} 章...")

    # Load chapter outline
    outline = load_chapter_outline(volume_id, chapter_id)
    if not outline:
        print(f"[ERROR] 找不到章节大纲: vol_{volume_id:02d} ch_{chapter_id:03d}")
        return ""

    chapter_title = outline.get("title", f"第{chapter_id}章")
    overview = outline.get("overview", "")
    entity_list = outline.get("entity_list", [])

    print(f"  章节: {chapter_title}")
    print(f"  概述: {overview[:50]}...")
    print(f"  参与者: {', '.join(entity_list)}")

    # Load context entities
    entities = load_entity_cards(entity_list)
    world_setting = load_world_setting()
    prev_chapter = load_previous_chapter(volume_id, chapter_id)
    history_chapters = load_history_chapters(volume_id, chapter_id, count=3)
    next_outline = load_next_chapter_outline(volume_id, chapter_id)
    writing_guide = load_writing_guide(volume_id)

    # Build prompt with @DSL context
    prompt_parts = [
        f"【章节大纲】:\n标题：{chapter_title}\n概述：{overview}\n",
        f"【参与者实体】:\n角色：{json.dumps(entities['characters'], ensure_ascii=False, indent=2)}\n",
        f"【场景】: {json.dumps(entities['scenes'], ensure_ascii=False, indent=2)}\n",
        f"【组织】: {json.dumps(entities['organizations'], ensure_ascii=False, indent=2)}\n",
    ]

    # Add world setting
    if world_setting:
        content = world_setting.get("content", world_setting)
        prompt_parts.append(f"【世界观设定】:\n{content.get('world_view', '')}\n")
        prompt_parts.append(f"【势力】:\n{json.dumps(content.get('major_power_camps', []), ensure_ascii=False, indent=2)}\n")

    # Add history chapters context (last 3 chapters)
    if history_chapters:
        prompt_parts.append(f"【历史章节剧情回顾】:\n{history_chapters}\n")

    # Add previous chapter context (immediate preceding chapter)
    if prev_chapter:
        prompt_parts.append(f"【前章结尾】:\n{prev_chapter}\n")

    # Add next chapter outline for continuity
    if next_outline:
        next_title = next_outline.get("title", "")
        next_overview = next_outline.get("overview", "")
        prompt_parts.append(f"【下一章预告】:\n{next_title}：{next_overview}\n")

    # Add writing guide
    if writing_guide:
        prompt_parts.append(f"【写作指南】:\n{writing_guide}\n")

    prompt_parts.append(
        f"【写作要求】:\n"
        f"1. 必须以【章节标题】作为正文第一行（格式：# 第X章 标题名）\n"
        f"2. 开头必须承接【前章结尾】的剧情和情绪，不能突兀跳到新场景\n"
        f"3. 严格按照章节大纲展开剧情，但要在细节上与历史章节呼应\n"
        f"4. 参与者只能使用提供的角色、场景、组织\n"
        f"5. 字数约6000字，不要过度水字数\n"
        f"6. 直接输出小说正文，不要分析或总结\n\n"
        f"请开始写作：\n"
    )

    prompt = "\n".join(prompt_parts)

    # Emit hook for skill injection
    beat_data = {"chapter_id": chapter_id, "title": chapter_title, "overview": overview}
    prompt_parts = [prompt]
    prompt_parts = event_bus.emit_pipeline("on_before_scene_write", prompt_parts, beat_data)
    prompt = "\n".join(prompt_parts)

    # Progressive saving callback
    def on_progress(ch_id, accumulated, char_count):
        if state_manager and ch_id:
            state_manager.update_progress(ch_id, char_count)
            # Save to temp file
            temp_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{ch_id:03d}_temp.md"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(accumulated)

    # Generate content with progressive saving
    writer = ProgressiveWriter(on_progress=on_progress, chunk_size=get_config("writing.progress_chunk_size", 1000))
    content = writer.write(prompt, chapter_id=chapter_id)

    return content


def review_chapter_content(volume_id: int, chapter_id: int, content: str, outline: dict) -> str:
    """
    Review chapter content for:
    1. Missing title - add from outline
    2. Word count check (using config.json settings)
    3. Content too short - flag for rewrite

    Returns tuple: (reviewed_content, needs_rewrite, issues)
    """
    issues = []

    # Get config values
    target_word_count = get_config("writing.target_word_count", 6000)
    min_word_count = get_config("writing.min_word_count", 4000)
    max_word_count = get_config("writing.max_word_count", 9000)
    auto_fix_title = get_config("review.auto_fix_title", True)
    word_count_check = get_config("review.word_count_check", True)

    # Check if title exists (first line should be # 第X章 xxx)
    title_pattern = r'^#\s*第\d+章\s+.+'
    if not re.match(title_pattern, content.strip()):
        if auto_fix_title:
            chapter_title = outline.get("title", f"第{chapter_id}章") if outline else f"第{chapter_id}章"
            content = f"# 第{chapter_id}章 {chapter_title}\n\n{content}"
            issues.append(f"[审阅] 缺少章节标题，已自动添加：第{chapter_id}章 {chapter_title}")
        else:
            issues.append(f"[审阅] 缺少章节标题")

    # Check word count (code-based)
    if word_count_check:
        word_count = count_chinese_words(content)
        if word_count < min_word_count:
            issues.append(f"[审阅] 字数不足（{word_count}字），低于{min_word_count}字下限")
            return content, True, issues
        elif word_count > max_word_count:
            issues.append(f"[审阅] 字数过多（{word_count}字），超过{max_word_count}字上限")
            return content, True, issues
        elif word_count < target_word_count * 0.9:
            issues.append(f"[审阅] 字数偏少（{word_count}字），目标{target_word_count}字")
        else:
            issues.append(f"[审阅] 字数检查通过（{word_count}字）")

    # Check for obvious logical issues
    first_lines = content.strip().split('\n')[:5]
    if len(first_lines) < 3:
        issues.append("[审阅] 正文开头内容过少")
        return content, True, issues

    return content, False, issues


def count_chinese_words(text: str) -> int:
    """
    Count words in mixed Chinese/English text.
    - Chinese characters: each character counts as one word
    - English words: split by whitespace, each word counts as one
    - Punctuation is ignored
    """
    import re

    # Remove markdown title if present
    text = re.sub(r'^#\s*第\d+章\s+.+\n?', '', text)

    # Count Chinese characters (each Chinese char is a word)
    chinese_chars = len(re.findall(r'[一-鿿　-〿＀-￯]', text))

    # Count English words (sequences of letters/digits)
    english_words = len(re.findall(r'[a-zA-Z0-9]+', text))

    # Total word count
    return chinese_chars + english_words


def deep_review_chapter(content: str, outline: dict, entity_list: List[str]) -> dict:
    """
    Deep review of chapter content vs outline.
    Returns: {needs_rewrite: bool, guidance: str, issues: List[str]}
    """
    # Check if deep review is enabled
    if not get_config("review.deep_review_enabled", True):
        return {"needs_rewrite": False, "issues": [], "guidance": "", "missing_events": [], "wrong_events": []}

    from utils.llm_client import generate_json
    from pydantic import BaseModel
    from typing import List

    class ReviewResult(BaseModel):
        needs_rewrite: bool
        issues: List[str]
        guidance: str
        missing_events: List[str]
        wrong_events: List[str]

    prompt = f"""你是网络小说编辑。请审阅以下章节内容，与大纲进行对比。

【章节大纲】：
标题：{outline.get('title', '')}
概述：{outline.get('overview', '')}

【章节正文】：
{content[:3000]}...（正文已截断）

【参与者实体】：
{', '.join(entity_list)}

请检查：
1. 大纲中的核心事件是否在正文中出现
2. 正文是否有偏离大纲设定的事件
3. 角色行为是否与设定矛盾
4. 场景描写是否符合要求

输出JSON：
{{"needs_rewrite": true/false, "issues": ["问题1", "问题2"], "guidance": "重新写作的指导建议", "missing_events": ["遗漏事件1"], "wrong_events": ["偏离事件1"]}}
"""

    try:
        result = generate_json(prompt, ReviewResult)
        if hasattr(result, 'model_dump'):
            return result.model_dump()
        return result if isinstance(result, dict) else {"needs_rewrite": False, "issues": [], "guidance": "", "missing_events": [], "wrong_events": []}
    except Exception as e:
        print(f"[WARN] 深度审阅失败: {e}")
        return {"needs_rewrite": False, "issues": [], "guidance": "", "missing_events": [], "wrong_events": []}


def save_chapter_content(volume_id: int, chapter_id: int, content: str, outline: dict = None):
    """Save chapter content to file, with review."""
    save_dir = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}"
    save_dir.mkdir(parents=True, exist_ok=True)

    # Load outline if not provided
    if outline is None:
        outline = load_chapter_outline(volume_id, chapter_id)

    entity_list = outline.get("entity_list", []) if outline else []

    # Basic review: check title, content length
    reviewed_content, basic_needs_rewrite, basic_issues = review_chapter_content(volume_id, chapter_id, content, outline)

    # Log basic issues
    for issue in basic_issues:
        print(f"  {issue}")

    # Deep review for content coherence (only if basic check passed)
    deep_review_result = {"needs_rewrite": False, "issues": [], "guidance": ""}
    if not basic_needs_rewrite:
        deep_review_result = deep_review_chapter(reviewed_content, outline, entity_list)
        if deep_review_result.get("needs_rewrite"):
            print(f"  [审阅] 发现严重问题：{', '.join(deep_review_result.get('issues', []))}")
            print(f"  [审阅] 指导意见：{deep_review_result.get('guidance', '')}")

    # Determine if rewrite is needed
    final_needs_rewrite = basic_needs_rewrite or deep_review_result.get("needs_rewrite", False)

    # Save content
    final_path = save_dir / f"ch_{chapter_id:03d}_final.md"
    with open(final_path, 'w', encoding='utf-8') as f:
        f.write(reviewed_content)

    if final_needs_rewrite:
        print(f"[⚠] 第 {chapter_id} 章标记为需要检查")
        return str(final_path), True, deep_review_result.get("guidance", "")
    else:
        print(f"[✓] 第 {chapter_id} 章成稿已保存至 {final_path}")
        return str(final_path), False, ""


def run_scene_writer(volume_id: int, start_chapter: int, end_chapter: int):
    """
    Main entry point for scene writing.
    Generates chapters from start_chapter to end_chapter.
    Uses state machine for progress tracking and supports resume from interruption.
    """
    state_manager = get_state_manager(volume_id)
    completed = 0
    failed = 0

    # Register chapters that need to be generated
    for chapter_id in range(start_chapter, end_chapter + 1):
        state = state_manager.get_state(chapter_id)
        if state.state == STATE_COMPLETED:
            # Check if file actually exists
            save_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id:03d}_final.md"
            if save_path.exists() and save_path.stat().st_size > 1000:
                print(f"[Skip] 第 {chapter_id} 章已完成，跳过")
                continue
            else:
                # File doesn't exist, mark as pending
                state.state = STATE_PENDING

    for chapter_id in range(start_chapter, end_chapter + 1):
        state = state_manager.get_state(chapter_id)

        # Skip if already completed
        save_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id:03d}_final.md"
        if save_path.exists() and save_path.stat().st_size > 1000:
            print(f"[Skip] 第 {chapter_id} 章已存在，跳过")
            continue

        # Check for temp file (resume from interruption)
        temp_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id:03d}_temp.md"
        if temp_path.exists():
            print(f"[Resume] 检测到第 {chapter_id} 章的临时文件，将继续生成")
            # Delete temp file to restart fresh
            temp_path.unlink()

        print(f"\n{'='*60}")
        print(f"[INFO] 启动场景子智能体集群，目标：卷 {volume_id} 章 {chapter_id}")
        print(f"{'='*60}")

        # Mark as generating
        state_manager.mark_generating(chapter_id)

        try:
            # Generate chapter content (with progressive saving)
            content = generate_chapter_content(volume_id, chapter_id, state_manager)

            if content:
                # Save chapter (returns path, needs_rewrite, guidance)
                save_result = save_chapter_content(volume_id, chapter_id, content)
                if isinstance(save_result, tuple):
                    final_path, needs_rewrite, guidance = save_result
                else:
                    final_path = save_result
                    needs_rewrite = False
                    guidance = ""

                # Mark as completed
                state_manager.mark_completed(chapter_id)

                # Delete temp file if exists
                if temp_path.exists():
                    temp_path.unlink()

                # Emit after scene write hook
                beat_data = {"chapter_id": chapter_id, "beats": [], "needs_rewrite": needs_rewrite, "guidance": guidance}
                event_bus.emit("on_after_scene_write", beat_data, content)

                # Track entity states for this chapter
                from core.entity_tracker import track_chapter_entities
                track_chapter_entities(volume_id, chapter_id)

                completed += 1
            else:
                state_manager.mark_failed(chapter_id, "内容为空")
                failed += 1
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] 第 {chapter_id} 章生成失败: {error_msg}")
            state_manager.mark_failed(chapter_id, error_msg)
            failed += 1

    print(f"\n{'='*60}")
    print(f"[INFO] 本批次生成完成：成功 {completed} 章，失败 {failed} 章")
    print(f"[INFO] 可通过重新运行命令继续生成失败的章节")
    print(f"{'='*60}")


# ============================================================================
# Continuation Support (for later use)
# ============================================================================

def continue_chapter(volume_id: int, chapter_id: int, target_words: int = 3000) -> str:
    """
    Continue writing a chapter to reach target word count.
    Used for continuation mode similar to NovelForge's extension feature.
    """
    # Load current chapter content
    path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id:03d}_final.md"
    if not path.exists():
        print(f"[ERROR] 找不到章节文件: {path}")
        return ""

    with open(path, 'r', encoding='utf-8') as f:
        current_content = f.read()

    current_words = len(current_content)
    if current_words >= target_words:
        print(f"[INFO] 章节字数已达标 ({current_words} >= {target_words})")
        return current_content

    remaining = target_words - current_words
    print(f"[INFO] 续写章节，目标增加约 {remaining} 字...")

    # Load chapter outline for context
    outline = load_chapter_outline(volume_id, chapter_id)
    next_outline = load_next_chapter_outline(volume_id, chapter_id)

    # Build continuation prompt
    prompt_parts = [
        f"【当前章节内容】:\n{current_content[-1000:]}\n",
        f"【章节大纲】:\n{outline.get('overview', '')}\n",
    ]

    if next_outline:
        prompt_parts.append(f"【下一章预告】:\n{next_outline.get('title', '')}: {next_outline.get('overview', '')}\n")

    prompt_parts.append(
        f"【续写要求】:\n"
        f"请继续上一段的剧情，续写约 {remaining} 字。\n"
        f"保持与前文的风格和节奏一致。\n"
        f"直接输出续写内容，不要分析。\n"
    )

    prompt = "\n".join(prompt_parts)

    # Generate continuation
    continuation = generate_stream(prompt)

    # Combine and save
    new_content = current_content + "\n\n" + continuation
    save_chapter_content(volume_id, chapter_id, new_content)

    return new_content


# ============================================================================
# Batch Mode (for compatibility)
# ============================================================================

def generate_batch_jsonl(volume_id: int, start_chap: int, end_chap: int, output_jsonl: str):
    """Generate batch JSONL for chapter outlines (not beats)."""
    requests = []

    for chapter_id in range(start_chap, end_chap + 1):
        outline = load_chapter_outline(volume_id, chapter_id)
        if not outline:
            continue

        custom_id = f"v{volume_id:02d}_ch{chapter_id:03d}"

        # Build prompt similar to generate_chapter_content
        prompt_parts = [
            f"【章节大纲】:\n标题：{outline.get('title', '')}\n概述：{outline.get('overview', '')}\n",
        ]

        # Inject entity context
        entity_list = outline.get("entity_list", [])
        entities = load_entity_cards(entity_list)
        if entities["characters"]:
            prompt_parts.append(f"【角色】: {json.dumps(entities['characters'], ensure_ascii=False)}\n")
        if entities["scenes"]:
            prompt_parts.append(f"【场景】: {json.dumps(entities['scenes'], ensure_ascii=False)}\n")

        # Add writing guide
        writing_guide = load_writing_guide(volume_id)
        if writing_guide:
            prompt_parts.append(f"【写作指南】: {writing_guide}\n")

        prompt_parts.append("请根据章节大纲创作正文，约6000字。直接输出正文。")

        request_obj = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v4/chat/completions",
            "body": {
                "model": "glm-4",
                "messages": [{"role": "user", "content": "\n".join(prompt_parts)}],
                "temperature": 0.85
            }
        }
        requests.append(request_obj)

    with open(output_jsonl, 'w', encoding='utf-8') as f:
        for req in requests:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")

    print(f"[✓] 已生成包含 {len(requests)} 个请求的 Batch 文件: {output_jsonl}")


def process_batch_results(result_jsonl: str):
    """Process batch results and save chapters."""
    if not os.path.exists(result_jsonl):
        print(f"[ERROR] 找不到结果文件: {result_jsonl}")
        return

    chapters_map = {}

    with open(result_jsonl, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            custom_id = data["custom_id"]
            try:
                content = data["response"]["body"]["choices"][0]["message"]["content"]
            except (KeyError, TypeError):
                content = "（该段场景生成失败）"

            chapters_map[custom_id] = content

    for custom_id, content in chapters_map.items():
        # Parse custom_id: v01_ch001
        parts = custom_id.split("_")
        vol_id = int(parts[0][1:])
        ch_id = int(parts[1][2:])

        save_chapter_content(vol_id, ch_id, content)


def get_world_context() -> str:
    """Get world context for backward compatibility."""
    from core.context_assembler import assemble_context
    path = Path(SETTINGS_DIR) / "world_setting.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""