"""
Volume Planner - Stage-level planning with rhythm control

Following NovelForge's approach:
1. plan - Generate 10 volume outlines with stage_count
2. plan --volume N - Generate stage outlines for volume N (not directly chapters)

Each stage follows NovelForge's rhythm control:
- Stage 1: Setup (main line starts, 1 subplot foreshadow)
- Stage 2: First push (surface progress, bigger resistance)
- Stage 3: Mid-section (risk escalation, main ≤50%)
- Stage 4: Mid-point turn (new resistance, can't resolve main)
- Stage 5: Crisis (core resources limited)
- Stage 6: Climax & resolution (within volume level)
"""

import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from utils.config import SETTINGS_DIR, VOLUMES_DIR, MANUSCRIPTS_DIR
from utils.llm_client import generate_json
from core.context_assembler import assemble_context


# ============================================================================
# Schema Definitions
# ============================================================================

class VolumeOutlineSchema(BaseModel):
    volume_id: int
    volume_name: str
    word_count_target: int = 250000
    stage_count: int = 6  # NovelForge-style stages
    main_target: str  # 卷主线目标
    branch_line: str = ""  # 辅线
    power_level_cap: str
    new_character_cards: List[Dict] = Field(default_factory=list)
    new_scene_cards: List[Dict] = Field(default_factory=list)
    entity_action_list: str = ""  # 卷末实体状态快照


class VolumeOutlinesSchema(BaseModel):
    volumes: List[VolumeOutlineSchema]


class ChapterOutlineSchema(BaseModel):
    chapter_number: int
    title: str
    overview: str
    entity_list: List[str] = Field(default_factory=list)  # participants


class StageOutlineSchema(BaseModel):
    stage_number: int
    stage_name: str
    reference_chapter: List[int]  # [start, end] chapter numbers
    analysis: str
    overview: str
    entity_snapshot: str
    chapter_outline_list: List[ChapterOutlineSchema]
    # Rhythm control fields
    stage_goal: str = ""  # 面向问题的陈述
    main_line_progress: str = ""  # 主线推进点
    subplot_insert: str = ""  # 辅线穿插点
    conflict_point: str = ""  # 冲突与反转
    suspense_hook: str = ""  # 跨阶段悬念


class VolumeStagesSchema(BaseModel):
    volume_id: int
    volume_name: str
    stages: List[StageOutlineSchema]


# ============================================================================
# Context Gathering
# ============================================================================

def get_world_context() -> str:
    """Reads settings into a context string."""
    context = []
    for filename in ["world_rules.json", "power_levels.json", "main_characters.json", "factions.json"]:
        # Legacy file support
        path = Path(SETTINGS_DIR) / filename
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                context.append(f"### {filename}\n{f.read()}")

    # New card-based files
    for card_type in ["one_sentence", "story_outline", "world_setting", "core_blueprint"]:
        path = Path(SETTINGS_DIR) / f"{card_type}.json"
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                content = data.get("content", data)
                context.append(f"### {card_type}\n{json.dumps(content, ensure_ascii=False)}")

    return "\n".join(context)


def get_core_blueprint() -> dict:
    """Load core blueprint for context."""
    path = Path(SETTINGS_DIR) / "core_blueprint.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


# ============================================================================
# Macro Planning (plan command without --volume)
# ============================================================================

def plan_macro_outlines(total_volumes: int = 10):
    """
    Generate macro outlines for all volumes (10 volumes by default).
    Each volume includes stage_count for NovelForge-style rhythm control.
    """
    print(f"[INFO] 正在生成 {total_volumes} 卷宏观大纲...")

    blueprint = get_core_blueprint()
    world_context = get_world_context()

    prompt = f"""你是顶尖网络小说架构师。请根据以下全局设定，规划 {total_volumes} 卷的核心大纲。
确保战力递进合理，不崩坏。每卷字数目标约 250000 字。

【世界观与设定】:
{world_context}

【核心蓝图】:
卷数: {blueprint.get('content', {}).get('volume_count', total_volumes)}

请为每卷输出：卷号、卷名、核心冲突、战力天花板、阶段数量（建议6个阶段）、主线目标、辅线。

"""
    schema_model = VolumeOutlinesSchema
    data = generate_json(prompt, schema_model)

    data_dict = data if isinstance(data, dict) else data.model_dump()
    data_list = [data_dict]
    data_list = event_bus_emit_pipeline("on_volume_planning", data_list)
    data_dict = data_list[0] if data_list else data_dict

    for vol in data_dict.get("volumes", []):
        vol_id = vol["volume_id"]
        path = Path(VOLUMES_DIR) / f"vol_{vol_id:02d}_outline.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(vol, f, ensure_ascii=False, indent=2)

    print(f"[✓] {len(data_dict.get('volumes', []))} 卷宏观大纲已生成并落盘。")


def event_bus_emit_pipeline(event_name: str, initial_data: Any, *args, **kwargs) -> Any:
    """Placeholder for event bus pipeline - will be connected to real event_bus when available."""
    from core.event_bus import event_bus
    return event_bus.emit_pipeline(event_name, initial_data, *args, **kwargs)


# ============================================================================
# Micro Planning (plan --volume N)
# ============================================================================

def plan_volume_stages(volume_id: int):
    """
    Generate stage outlines for a specific volume (not 50 chapters directly).
    Following NovelForge's volume → stage → chapter hierarchy.

    Each volume has multiple stages, each stage contains multiple chapter outlines.
    """
    print(f"[INFO] 启动分卷调度器，目标：第 {volume_id} 卷阶段大纲...")

    vol_path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_outline.json"
    if not vol_path.exists():
        print(f"[ERROR] 找不到卷 {volume_id} 的大纲，请先执行宏观规划！")
        return False

    with open(vol_path, 'r', encoding='utf-8') as f:
        vol_outline = json.load(f)

    world_context = get_world_context()
    blueprint = get_core_blueprint()

    # Get characters, scenes, organizations from core_blueprint
    content = blueprint.get("content", blueprint)
    characters = content.get("character_cards", [])
    scenes = content.get("scene_cards", [])
    organizations = content.get("organization_cards", [])

    stage_count = vol_outline.get("stage_count", 6)
    prompt = f"""你是网文白金主编。当前任务是为第 {volume_id} 卷设计 {stage_count} 个阶段的细纲。

【卷信息】:
- 卷名：{vol_outline.get('volume_name', '')}
- 主线目标：{vol_outline.get('main_target', '')}
- 辅线：{vol_outline.get('branch_line', '')}
- 战力天花板：{vol_outline.get('power_level_cap', '')}

【全局设定参考】:
{world_context}

【角色卡】:
{json.dumps(characters, ensure_ascii=False, indent=2)}

【场景卡】:
{json.dumps(scenes, ensure_ascii=False, indent=2)}

【组织卡】:
{json.dumps(organizations, ensure_ascii=False, indent=2)}

【节奏控制要求】（强约束）:
- 本卷共 {stage_count} 个阶段
- 阶段1：开端/铺垫/诱发事件（主线仅"启动"，不要解决核心矛盾）
- 阶段2：第一次推进（表面进展但引出更大阻力）
- 阶段3：中段推进（风险升级，主线达成度≤50%）
- 阶段4：中点/重大转折（新的阻力来源）
- 阶段5：危机/失利（核心资源受限）
- 阶段6：卷内高潮与阶段性收束（主线达成但保留更高层悬念）

每个阶段必须包含：
1. 阶段目标（面向问题的陈述）
2. 主线推进点（≤该阶段允许的推进幅度）
3. 辅线穿插点
4. 冲突与反转
5. 悬念钩子（跨到下一阶段的问题）
6. 参与的实体列表
7. 该阶段的章节大纲列表（每个章节大纲需包含章节号、标题、概述、参与者实体列表）

每章的字数目标约6000字，请确保章节大纲足够丰富支撑扩写。

【重要】每卷需要生成约100章节的大纲！请按以下分配：
- 每个阶段生成15-18个章节大纲
- 6个阶段共生成90-108个章节大纲（目标100章）
- 章节编号连续递增（第1卷从1开始）
"""
    schema_model = VolumeStagesSchema
    data = generate_json(prompt, schema_model)

    data_dict = data if isinstance(data, dict) else data.model_dump()

    # Save volume stages
    vol_stages_dir = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_stages"
    vol_stages_dir.mkdir(parents=True, exist_ok=True)

    for stage in data_dict.get("stages", []):
        stage_num = stage["stage_number"]
        stage_path = vol_stages_dir / f"stage_{stage_num:02d}.json"
        with open(stage_path, 'w', encoding='utf-8') as f:
            json.dump(stage, f, ensure_ascii=False, indent=2)

        # Also create individual chapter outline files for each stage
        chapter_dir = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_chapters"
        chapter_dir.mkdir(parents=True, exist_ok=True)

        for ch_outline in stage.get("chapter_outline_list", []):
            ch_num = ch_outline["chapter_number"]
            ch_path = chapter_dir / f"ch_{ch_num:03d}_outline.json"
            with open(ch_path, 'w', encoding='utf-8') as f:
                json.dump(ch_outline, f, ensure_ascii=False, indent=2)

    print(f"[✓] 第 {volume_id} 卷 {stage_count} 个阶段大纲已生成并落盘。")
    print(f"    共生成 {len(data_dict.get('stages', []))} 个阶段")
    return True


# ============================================================================
# Legacy Support (for backward compatibility)
# ============================================================================

# Keep the old function names as aliases for compatibility
def plan_macro_outlines_alias(total_volumes: int = 10):
    plan_macro_outlines(total_volumes)


def run_volume_planner(volume_id: int = None):
    if volume_id is None:
        plan_macro_outlines()
    else:
        plan_volume_stages(volume_id)