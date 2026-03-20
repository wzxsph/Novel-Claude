import os
import json
from typing import List, Optional
from pydantic import BaseModel
from utils.config import SETTINGS_DIR
from utils.llm_client import generate_json

# Define strict Pydantic Schemas for World Building

class Faction(BaseModel):
    name: str
    description: str
    key_figures: List[str]

class FactionsSchema(BaseModel):
    factions: List[Faction]

class PowerLevel(BaseModel):
    level_id: int
    name: str
    lifespan_limit: Optional[int]
    combat_capability: str
    upgrade_condition: str

class PowerLevelsSchema(BaseModel):
    system_name: str
    levels: List[PowerLevel]

class Character(BaseModel):
    name: str
    role: str
    background: str
    personality: str
    power_level: str
    current_goal: str

class CharactersSchema(BaseModel):
    characters: List[Character]

class WorldRule(BaseModel):
    rule_name: str
    description: str
    impact_on_plot: str

class WorldRulesSchema(BaseModel):
    rules: List[WorldRule]

SCHEMA_MAP = {
    "factions": FactionsSchema,
    "power_levels": PowerLevelsSchema,
    "main_characters": CharactersSchema,
    "world_rules": WorldRulesSchema
}

def save_setting_chunk(category: str, content: dict) -> str:
    """Save setting chunk to the settings directory"""
    target_path = os.path.join(SETTINGS_DIR, f"{category}.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
    return target_path

def render_to_markdown():
    """Renders the generated JSON files into a human-readable Markdown file."""
    md_lines = ["# 🌍 核心世界观设定手册 (World Manual)\n"]
    
    # Render Factions
    try:
        with open(os.path.join(SETTINGS_DIR, "factions.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            md_lines.append("## 🏛️ 势力分布\n")
            for fac in data.get("factions", []):
                md_lines.append(f"### {fac['name']}\n- **描述**: {fac['description']}\n- **关键人物**: {', '.join(fac['key_figures'])}\n")
    except FileNotFoundError:
        pass
        
    # Render Power Levels
    try:
        with open(os.path.join(SETTINGS_DIR, "power_levels.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            md_lines.append(f"## ⚔️ 战力体系: {data.get('system_name', '未知体系')}\n")
            for lvl in data.get("levels", []):
                md_lines.append(f"### Lv.{lvl['level_id']} {lvl['name']}\n- **寿命限制**: {lvl.get('lifespan_limit', '无')}年\n- **战斗表现**: {lvl['combat_capability']}\n- **突破条件**: {lvl['upgrade_condition']}\n")
    except FileNotFoundError:
        pass

    # Render Characters
    try:
        with open(os.path.join(SETTINGS_DIR, "main_characters.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            md_lines.append("## 🎭 核心人物\n")
            for char in data.get("characters", []):
                md_lines.append(f"### {char['name']} ({char['role']})\n- **背景**: {char['background']}\n- **性格**: {char['personality']}\n- **当前境界**: {char['power_level']}\n- **当前目标**: {char['current_goal']}\n")
    except FileNotFoundError:
        pass

    # Render World Rules
    try:
        with open(os.path.join(SETTINGS_DIR, "world_rules.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            md_lines.append("## 📜 世界底层规则\n")
            for rule in data.get("rules", []):
                md_lines.append(f"### {rule['rule_name']}\n- **详细描述**: {rule['description']}\n- **对剧情的影响**: {rule['impact_on_plot']}\n")
    except FileNotFoundError:
        pass

    manual_path = os.path.join(SETTINGS_DIR, "world_manual.md")
    with open(manual_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    return manual_path

def run_world_builder(logline: str):
    """
    Harness 职责: 将人类模糊创意转化为强类型 JSON。
    """
    print(f"[INFO] 正在基于核心创意构建世界观：'{logline}'")
    REQUIRED_CATEGORIES = ["factions", "power_levels", "main_characters", "world_rules"]
    
    for category in REQUIRED_CATEGORIES:
        print(f"[s01] 正在生成 {category}...")
        prompt = f"核心创意：{logline}\n\n请为这个网文世界生成 `{category}` 相关设定。必须详实、有网文爽感和深度。"
        schema_model = SCHEMA_MAP[category]
        
        # This acts as the Agent validation loop inherently due to our generate_json retry logic
        content = generate_json(prompt, schema_model)
        saved_path = save_setting_chunk(category, content)
        print(f"  [✓] 保存成功: {saved_path}")
        
    md_path = render_to_markdown()
    print(f"[✓] 全局设定渲染完成: {md_path}")
    print("[!] Action Required: 请人工检查并确认 setting 目录下的设定文件，可直接修改 world_manual.md 和 JSON。")
