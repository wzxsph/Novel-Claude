"""Skill management handlers for the interactive REPL."""

from typing import Any, Dict, List

from utils import config


def handle(args: List[str]) -> Dict[str, Any]:
    return {"message": "Use: skills list|enable|disable|reload|build"}


def list_skills(args: List[str]) -> Dict[str, Any]:
    if args:
        return {"error": "Usage: skills list"}
    try:
        from core.runtime import get_runtime

        runtime = get_runtime()
        active = runtime.context.active_skills
        output = [f"Loaded {len(active)} skills:"]
        for name, skill in sorted(active.items()):
            output.append(f"  🟢 {skill.name} (skills/{name}/skill.py)")

        skills_dir = config.PROJECT_ROOT / "skills"
        for directory in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
            if directory.name in active or directory.name.startswith((".", "__")):
                continue
            label = "disabled" if (directory / ".disabled").exists() else "load error"
            output.append(f"  ⚠️ {directory.name} ({label})")
        return {"message": "\n".join(output)}
    except Exception as exc:
        return {"error": f"skills list failed: {exc}"}


def enable(args: List[str]) -> Dict[str, Any]:
    if len(args) != 1:
        return {"error": "Usage: skills enable <name>"}
    from core.runtime import get_runtime

    if not get_runtime().plugin_manager.enable_skill(args[0]):
        return {"error": f"Skill {args[0]} could not be enabled."}
    return {"message": f'Skill "{args[0]}" enabled.'}


def disable(args: List[str]) -> Dict[str, Any]:
    if len(args) != 1:
        return {"error": "Usage: skills disable <name>"}
    from core.runtime import get_runtime

    if not get_runtime().plugin_manager.disable_skill(args[0]):
        return {"error": f"Skill {args[0]} could not be disabled."}
    return {"message": f'Skill "{args[0]}" disabled.'}


def reload(args: List[str]) -> Dict[str, Any]:
    if len(args) > 1:
        return {"error": "Usage: skills reload [name]"}
    from core.runtime import get_runtime

    runtime = get_runtime()
    if args:
        if not runtime.plugin_manager.hot_reload(args[0]):
            return {"error": f"Skill {args[0]} could not be reloaded."}
    else:
        runtime.plugin_manager.unload_all()
        runtime.plugin_manager.scan_and_load()
    return {"message": f"Loaded {len(runtime.context.active_skills)} skills."}


def build(args: List[str]) -> Dict[str, Any]:
    if not args:
        return {"error": "Usage: skills build <request>"}
    try:
        from core.agents.skill_builder_agent import SkillBuilderAgent
        from core.runtime import get_runtime

        runtime = get_runtime()
        agent = SkillBuilderAgent(runtime.context, runtime.plugin_manager)
        if agent.build_skill(" ".join(args)):
            return {"message": "Skill built and reloaded successfully."}
        return {"error": "Skill build failed. Check logs for details."}
    except Exception as exc:
        return {"error": f"skills build failed: {exc}"}
