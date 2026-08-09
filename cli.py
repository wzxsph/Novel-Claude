"""Novel-Claude one-shot CLI entry point."""

from __future__ import annotations

import sys

import click


if "--interactive" in sys.argv or "-i" in sys.argv:
    from cli.repl import start_repl

    start_repl()
    raise SystemExit(0)


def _emit_result(result: dict):
    if result.get("error"):
        raise click.ClickException(str(result["error"]))
    if result.get("message"):
        click.echo(result["message"])
    if result.get("output"):
        click.echo(result["output"])


def _wait_for_tasks():
    from utils.config import wait_for_background_tasks

    wait_for_background_tasks()


@click.group()
def cli():
    """Novel-Claude V3 — experimental agentic novel generation CLI."""
    from utils import config

    current_project = config.NOVEL_NAME or "Default"
    click.echo(click.style(f"当前激活项目: {current_project}", fg="cyan", bold=True))


def _ensure_runtime():
    """Load Skills only for commands whose execution uses lifecycle hooks."""
    from core.runtime import get_runtime

    return get_runtime()


@cli.command()
@click.argument("logline")
def init(logline: str):
    """Run the complete world-building pipeline from a LOGLINE."""
    from cli.commands.novel_commands import init as run

    _emit_result(run([logline]))
    _wait_for_tasks()


@cli.command()
def expand():
    """Regenerate the story outline from initialized setting cards."""
    from cli.commands.novel_commands import expand as run

    _emit_result(run([]))
    _wait_for_tasks()


@cli.command()
def world():
    """Regenerate the world setting from the story outline."""
    from cli.commands.novel_commands import world as run

    _emit_result(run([]))
    _wait_for_tasks()


@cli.command()
def blueprint():
    """Regenerate character, scene, and organization cards."""
    from cli.commands.novel_commands import blueprint as run

    _emit_result(run([]))
    _wait_for_tasks()


@cli.command()
@click.argument("volume_arg", required=False, type=click.IntRange(min=1))
@click.option("--volume", "volume_option", type=click.IntRange(min=1))
def plan(volume_arg: int | None, volume_option: int | None):
    """Plan all volumes, or one volume via `plan 1` / `plan --volume 1`."""
    if volume_arg is not None and volume_option is not None:
        raise click.UsageError("卷号只能指定一次")
    volume = volume_option if volume_option is not None else volume_arg
    _ensure_runtime()
    from cli.commands.novel_commands import plan as run

    _emit_result(run([] if volume is None else [str(volume)]))
    _wait_for_tasks()


@cli.command()
@click.option("--volume", type=click.IntRange(min=1), required=True)
@click.option("--chapters", required=True, help='章节范围，如 "1-5" 或 "1"。')
def write(volume: int, chapters: str):
    """Generate chapters with progressive saving and enabled Skills."""
    _ensure_runtime()
    from cli.commands.novel_commands import write as run

    _emit_result(run(["--volume", str(volume), "--chapters", chapters]))
    _wait_for_tasks()


@cli.command("batch-build")
@click.option("--volume", type=click.IntRange(min=1), required=True)
@click.option("--chapters", required=True)
def batch_build(volume: int, chapters: str):
    """Build a Zhipu Batch API JSONL request file."""
    from cli.commands.novel_commands import batch_build as run

    _emit_result(run(["--volume", str(volume), "--chapters", chapters]))


@cli.command("batch-submit")
@click.argument("jsonl_path", type=click.Path(exists=True, dir_okay=False))
def batch_submit(jsonl_path: str):
    """Submit a JSONL file to the Zhipu Batch API."""
    from cli.commands.novel_commands import batch_submit as run

    _emit_result(run([jsonl_path]))


@cli.command("batch-sync")
@click.argument("batch_id")
def batch_sync(batch_id: str):
    """Poll and merge a Zhipu Batch API job."""
    from cli.commands.novel_commands import batch_sync as run

    _emit_result(run([batch_id]))
    _wait_for_tasks()


@cli.command()
@click.option("--volume", type=click.IntRange(min=1), required=True)
@click.option("--chapters", required=True)
def reindex(volume: int, chapters: str):
    """Reindex completed chapters into the enabled RAG Skill."""
    _ensure_runtime()
    from cli.commands.novel_commands import reindex as run

    _emit_result(run(["--volume", str(volume), "--chapters", chapters]))
    _wait_for_tasks()


@cli.command()
@click.option("--stage", type=click.IntRange(min=1))
@click.option("--chapter", type=click.IntRange(min=1))
def audit(stage: int | None, chapter: int | None):
    """Audit one stage or one chapter for consistency."""
    if (stage is None) == (chapter is None):
        raise click.UsageError("请且仅请指定 --stage 或 --chapter")
    from cli.commands.novel_commands import audit as run

    args = ["--stage", str(stage)] if stage is not None else ["--chapter", str(chapter)]
    _emit_result(run(args))


@cli.command()
@click.option("--volume", type=click.IntRange(min=1), required=True)
@click.option("--chapter", type=click.IntRange(min=1), required=True)
def track(volume: int, chapter: int):
    """Track entity state changes for a generated chapter."""
    from cli.commands.novel_commands import track as run

    _emit_result(run(["--volume", str(volume), "--chapter", str(chapter)]))


@cli.command()
@click.option(
    "-f",
    "--files",
    multiple=True,
    required=True,
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("-i", "--instruction", required=True)
def review(files: tuple[str, ...], instruction: str):
    """Use the configured model to review and rewrite selected files."""
    from cli.commands.agent_commands import review as run

    args = []
    for file_path in files:
        args.extend(["-f", file_path])
    args.extend(["-i", instruction])
    _emit_result(run(args))
    _wait_for_tasks()


@cli.group()
def skills():
    """List, enable, disable, reload, or generate Skills."""


@skills.command("list")
def skills_list():
    from core.runtime import get_runtime
    from utils import config

    runtime = get_runtime()
    active = runtime.context.active_skills
    if active:
        click.echo(click.style(f"\n🔌 已加载 {len(active)} 个插件:", fg="green", bold=True))
        for name, skill in sorted(active.items()):
            click.echo(f"  🟢 {skill.name} (skills/{name}/skill.py)")
    else:
        click.echo("\n🔌 暂无已加载插件")

    skills_dir = config.PROJECT_ROOT / "skills"
    for directory in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
        if directory.name in active or directory.name.startswith((".", "__")):
            continue
        state = "🔴 已禁用" if (directory / ".disabled").exists() else "⚠️ 加载失败"
        click.echo(f"  {state}: skills/{directory.name}/")


@skills.command("enable")
@click.argument("name")
def skills_enable(name: str):
    from core.runtime import get_runtime

    if not get_runtime().plugin_manager.enable_skill(name):
        raise click.ClickException(f"无法启用插件 {name}")


@skills.command("disable")
@click.argument("name")
def skills_disable(name: str):
    from core.runtime import get_runtime

    if not get_runtime().plugin_manager.disable_skill(name):
        raise click.ClickException(f"无法禁用插件 {name}")


@skills.command("reload")
@click.argument("name", required=False)
def skills_reload(name: str | None):
    from core.runtime import get_runtime

    runtime = get_runtime()
    if name:
        if not runtime.plugin_manager.hot_reload(name):
            raise click.ClickException(f"无法重载插件 {name}")
    else:
        runtime.plugin_manager.unload_all()
        runtime.plugin_manager.scan_and_load()
    click.echo(f"[✓] 当前共加载 {len(runtime.context.active_skills)} 个插件。")


@skills.command("build")
@click.argument("request")
def skills_build(request: str):
    from core.agents.skill_builder_agent import SkillBuilderAgent
    from core.runtime import get_runtime

    runtime = get_runtime()
    agent = SkillBuilderAgent(runtime.context, runtime.plugin_manager)
    if not agent.build_skill(request):
        raise click.ClickException("插件生成失败，请查看日志")


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n[WARN] 收到停止信号，正在等待后台任务...")
    finally:
        _wait_for_tasks()
