# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
# Create virtual environment and install dependencies
uv venv
uv pip install -r requirements.txt
```

## Common Commands

```bash
# CLI mode (one-shot commands)
uv run python cli.py --help

# Interactive REPL mode
uv run python cli.py --interactive

# Run tests (if any)
pytest

# Development workflow
uv run python cli.py skills reload   # After modifying skills code
```

## Architecture

### Three-Stage Novel Generation Pipeline

1. **world_builder.py** - Initializes world settings (factions, power levels, characters, rules) from a logline
2. **volume_planner.py** - Plans 10-volume macro outline, then generates scene beats for each volume
3. **scene_writer.py** - Spawns subagents to write scenes, merges via Editor Agent

### Microkernel & Plugin System

The V3 architecture uses a plugin system (`skills/`) that hooks into the EventBus:

- **EventBus** (`core/event_bus.py`) - Central singleton for event dispatch with fault isolation
  - `emit()` - broadcast to all subscribers
  - `emit_pipeline()` - sequential chain (output → next input)
  - `collect()` - gather results from all skills

- **PluginManager** (`core/plugin_manager.py`) - Dynamically loads skills from `skills/` directory

- **BaseSkill** (`core/base_skill.py`) - Standard plugin base class with lifecycle hooks:
  - `on_init()` - after plugin loads
  - `on_before_scene_write()` - before each scene generation
  - `on_after_scene_write()` - after scene completes
  - `get_llm_tools()` - register AI tools

### Key Files

| File | Purpose |
|------|---------|
| `cli.py` | Click-based CLI entry, also hosts interactive REPL |
| `cli/repl.py` | Interactive REPL implementation |
| `cli/dispatcher.py` | Command routing for REPL |
| `cli/project_manager.py` | Multi-project state management |
| `core/agents/editor_agent.py` | ReAct-based chapter merger |
| `core/agents/skill_builder_agent.py` | Auto-generates new skills |
| `utils/llm_client.py` | ZhipuAI client with lazy initialization |

### Project Workspace

Projects are stored in `.novel_projects/.novel_{name}/` with subdirectories: `settings/`, `volumes/`, `manuscripts/`, `memory/`, `batch_jobs/`

## Skill Development

Skills live in `skills/{name}/skill.py` and must inherit from `BaseSkill`:

```python
from core.base_skill import BaseSkill

class MySkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "MySkill"

    def on_before_scene_write(self, prompt_payload, beat_data):
        prompt_payload.append("\n[System] Custom injection")
        return prompt_payload
```

After creating/modifying a skill, run `uv run python cli.py skills reload` to hot-reload.

## Pre-Push Security Check

Before every `git push`, always check for API key leaks:

```bash
# Check for leaked keys before pushing
git diff --cached --name-only | xargs grep -l "api_key\|API_KEY\|ANTHROPIC\|zhipuai" 2>/dev/null
git diff HEAD --name-only | xargs grep -l "api_key\|API_KEY\|ANTHROPIC\|zhipuai" 2>/dev/null

# Also check untracked files
grep -r "api_key\|API_KEY\|ANTHROPIC\|zhipuai" --include="*.py" --include="*.json" --include="*.env" . 2>/dev/null | grep -v ".venv" | grep -v "__pycache__"
```

If any secrets are found, remove them before pushing. The `env` file and `.novel_cli_config/` are in `.gitignore` but always verify.

## Pre-Push Workflow

Before every `git push`, always run:

```bash
uv run python scripts/pre_push.py
```

This script:
1. Updates `README.md` with current project structure
2. Checks for API key leaks in staged/unstaged/untracked files