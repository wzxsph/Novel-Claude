"""Novel workflow handlers shared by Click and the interactive REPL."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

from cli.project_manager import project_manager
from utils import config


def _error(message: str) -> Dict[str, Any]:
    return {"error": message}


def _parse_positive(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}必须是正整数") from exc
    if parsed < 1:
        raise ValueError(f"{label}必须大于 0")
    return parsed


def parse_chapter_range(value: str) -> tuple[int, int]:
    text = (value or "").strip()
    if not text:
        raise ValueError("必须提供章节范围")
    parts = text.split("-")
    if len(parts) == 1:
        chapter = _parse_positive(parts[0], "章节号")
        return chapter, chapter
    if len(parts) != 2:
        raise ValueError("章节范围格式应为 1 或 1-5")
    start = _parse_positive(parts[0], "起始章节")
    end = _parse_positive(parts[1], "结束章节")
    if start > end:
        raise ValueError("起始章节不能大于结束章节")
    return start, end


def _parse_volume_and_chapters(args: List[str]) -> tuple[int, int, int]:
    volume = None
    chapters = None
    index = 0
    while index < len(args):
        if args[index] == "--volume" and index + 1 < len(args):
            volume = _parse_positive(args[index + 1], "卷号")
            index += 2
        elif args[index] == "--chapters" and index + 1 < len(args):
            chapters = args[index + 1]
            index += 2
        else:
            raise ValueError(f"未知或不完整参数: {args[index]}")
    if volume is None or chapters is None:
        raise ValueError("用法: --volume N --chapters X-Y")
    start, end = parse_chapter_range(chapters)
    return volume, start, end


def handle(args: List[str]) -> Dict[str, Any]:
    return {"message": "Use: init, expand, world, blueprint, plan, write"}


def init(args: List[str]) -> Dict[str, Any]:
    if not args:
        return _error("用法: init <一句话创意>")
    try:
        from world_builder import run_world_builder

        config.ensure_workspace_dirs()
        if run_world_builder(" ".join(args)) is False:
            return _error("世界构建流程未完成，请查看前面的错误信息。")
        return {"message": "世界构建流程已完成。"}
    except Exception as exc:
        return _error(f"初始化失败: {exc}")


def expand(args: List[str]) -> Dict[str, Any]:
    if args:
        return _error("用法: expand")
    try:
        from world_builder import run_expand

        if run_expand() is False:
            return _error("缺少前置设定，请先运行 init。")
        return {"message": "故事大纲已更新。"}
    except Exception as exc:
        return _error(f"故事扩展失败: {exc}")


def world(args: List[str]) -> Dict[str, Any]:
    if args:
        return _error("用法: world")
    try:
        from world_builder import run_world

        if run_world() is False:
            return _error("缺少故事大纲，请先运行 expand。")
        return {"message": "世界观设定已更新。"}
    except Exception as exc:
        return _error(f"世界观生成失败: {exc}")


def blueprint(args: List[str]) -> Dict[str, Any]:
    if args:
        return _error("用法: blueprint")
    try:
        from world_builder import run_blueprint

        if run_blueprint() is False:
            return _error("缺少故事大纲或世界观，请先完成前置阶段。")
        return {"message": "核心蓝图已更新。"}
    except Exception as exc:
        return _error(f"蓝图生成失败: {exc}")


def plan(args: List[str]) -> Dict[str, Any]:
    try:
        volume = None
        if args:
            if len(args) == 2 and args[0] == "--volume":
                volume = _parse_positive(args[1], "卷号")
            elif len(args) == 1:
                volume = _parse_positive(args[0], "卷号")
            else:
                raise ValueError("用法: plan [N] 或 plan --volume N")

        if volume is None:
            from volume_planner import plan_macro_outlines

            plan_macro_outlines()
            return {"message": "全书分卷大纲已生成。"}

        from volume_planner import run_volume_planner

        if run_volume_planner(volume) is False:
            return _error(f"找不到第 {volume} 卷大纲，请先运行 plan。")
        project_manager.update_context(volume=volume)
        return {"message": f"第 {volume} 卷细纲已生成。"}
    except Exception as exc:
        return _error(f"规划失败: {exc}")


def write(args: List[str]) -> Dict[str, Any]:
    try:
        volume, start, end = _parse_volume_and_chapters(args)
        from scene_writer import run_scene_writer

        completed, failed = run_scene_writer(volume, start, end)
        project_manager.update_context(volume=volume, chapter=end)
        if failed:
            return _error(
                f"第 {volume} 卷生成结束：成功 {completed} 章，失败 {failed} 章。"
            )
        return {"message": f"第 {volume} 卷第 {start}-{end} 章生成任务已结束。"}
    except Exception as exc:
        return _error(f"写作失败: {exc}")


def batch(args: List[str]) -> Dict[str, Any]:
    if not args:
        return {"message": "Use: batch build|submit|sync"}
    handlers = {"build": batch_build, "submit": batch_submit, "sync": batch_sync}
    handler = handlers.get(args[0])
    if handler is None:
        return _error(f"未知 Batch 子命令: {args[0]}")
    return handler(args[1:])


def batch_build(args: List[str]) -> Dict[str, Any]:
    try:
        volume, start, end = _parse_volume_and_chapters(args)
        from scene_writer import generate_batch_jsonl

        output_path = Path(config.BATCH_DIR) / f"vol_{volume:02d}_ch_{start}_{end}_req.jsonl"
        request_count = generate_batch_jsonl(volume, start, end, str(output_path))
        if request_count == 0:
            return _error("未找到可构建的章节大纲，请先运行 plan --volume N。")
        return {"message": f"Batch JSONL 已生成: {output_path}"}
    except Exception as exc:
        return _error(f"Batch 构建失败: {exc}")


def batch_submit(args: List[str]) -> Dict[str, Any]:
    if len(args) != 1:
        return _error("用法: batch submit <jsonl_path>")
    jsonl_path = Path(args[0])
    if not jsonl_path.is_file():
        return _error(f"找不到文件: {jsonl_path}")
    try:
        from utils.batch_client import submit_batch_task

        batch_id = submit_batch_task(str(jsonl_path), desc=f"Submit: {jsonl_path.name}")
        return {"message": f"Batch 已提交，ID: {batch_id}"}
    except Exception as exc:
        return _error(f"Batch 提交失败: {exc}")


def batch_sync(args: List[str]) -> Dict[str, Any]:
    if len(args) != 1:
        return _error("用法: batch sync <batch_id>")
    batch_id = args[0]
    try:
        from scene_writer import process_batch_results
        from utils.batch_client import download_batch_results, get_batch_status

        print(f"[Batch] 正在监听任务 {batch_id} ...")
        while True:
            status = get_batch_status(batch_id)
            current_status = status.status
            print(f"  > 状态: {current_status}")
            if current_status == "completed":
                result_path = Path(config.BATCH_DIR) / f"{batch_id}_results.jsonl"
                error_path = Path(config.BATCH_DIR) / f"{batch_id}_errors.jsonl"
                if download_batch_results(batch_id, str(result_path), str(error_path)):
                    process_batch_results(str(result_path))
                return {"message": "Batch 结果已同步并合并。"}
            if current_status in {"failed", "cancelled", "expired"}:
                return _error(f"Batch 任务状态异常: {current_status}")
            time.sleep(60)
    except Exception as exc:
        return _error(f"Batch 同步失败: {exc}")


def reindex(args: List[str]) -> Dict[str, Any]:
    try:
        volume, start, end = _parse_volume_and_chapters(args)
        from core.event_bus import event_bus
        from core.runtime import get_runtime

        runtime = get_runtime()
        indexed = 0
        for chapter in range(start, end + 1):
            path = (
                Path(config.MANUSCRIPTS_DIR)
                / f"vol_{volume:02d}"
                / f"ch_{chapter:03d}_final.md"
            )
            if not path.exists():
                print(f"[WARN] 找不到成稿文件: {path}")
                continue
            runtime.context.set_current_ids(volume, chapter)
            content = path.read_text(encoding="utf-8")
            event_bus.emit("on_after_scene_write", {"chapter_id": chapter, "beats": []}, content)
            indexed += 1
        return {"message": f"已提交 {indexed} 章进行 RAG 重建。"}
    except Exception as exc:
        return _error(f"RAG 重建失败: {exc}")


def audit(args: List[str]) -> Dict[str, Any]:
    target_type = None
    target_id = None
    if len(args) == 2 and args[0] in {"--stage", "--chapter"}:
        target_type = args[0][2:]
        try:
            target_id = _parse_positive(args[1], "审核编号")
        except ValueError as exc:
            return _error(str(exc))
    else:
        return _error("用法: audit --stage N 或 audit --chapter N")

    try:
        import json

        from core.context_assembler import assemble_context
        from utils.llm_client import generate_stream

        volume = project_manager.current_volume or 1
        if target_type == "stage":
            data_path = (
                Path(config.VOLUMES_DIR)
                / f"vol_{volume:02d}_stages"
                / f"stage_{target_id:02d}.json"
            )
            prompt_path = config.PROJECT_ROOT / "prompts" / "阶段审核.txt"
            context_type = "stage_outline"
        else:
            data_path = (
                Path(config.VOLUMES_DIR)
                / f"vol_{volume:02d}_chapters"
                / f"ch_{target_id:03d}_outline.json"
            )
            prompt_path = config.PROJECT_ROOT / "prompts" / "章节审核.txt"
            context_type = "chapter_outline"

        if not data_path.exists():
            return _error(f"找不到审核目标: {data_path}")
        if not prompt_path.exists():
            return _error(f"找不到审核提示词: {prompt_path}")

        data = json.loads(data_path.read_text(encoding="utf-8"))
        if target_type == "chapter":
            manuscript = (
                Path(config.MANUSCRIPTS_DIR)
                / f"vol_{volume:02d}"
                / f"ch_{target_id:03d}_final.md"
            )
            data["content"] = manuscript.read_text(encoding="utf-8") if manuscript.exists() else ""

        prompt = prompt_path.read_text(encoding="utf-8")
        result = generate_stream(assemble_context(prompt, context_type, data))
        return {"output": result, "message": f"{target_type} {target_id} 审核完成。"}
    except Exception as exc:
        return _error(f"审核失败: {exc}")


def track(args: List[str]) -> Dict[str, Any]:
    volume = None
    chapter = None
    index = 0
    try:
        while index < len(args):
            if args[index] == "--volume" and index + 1 < len(args):
                volume = _parse_positive(args[index + 1], "卷号")
                index += 2
            elif args[index] == "--chapter" and index + 1 < len(args):
                chapter = _parse_positive(args[index + 1], "章节号")
                index += 2
            else:
                raise ValueError(f"未知或不完整参数: {args[index]}")
        if volume is None or chapter is None:
            raise ValueError("用法: track --volume N --chapter N")

        manuscript = (
            Path(config.MANUSCRIPTS_DIR)
            / f"vol_{volume:02d}"
            / f"ch_{chapter:03d}_final.md"
        )
        if not manuscript.is_file():
            return _error(f"找不到章节成稿: {manuscript}")

        from core.entity_tracker import track_chapter_entities

        track_chapter_entities(volume, chapter)
        return {"message": f"第 {chapter} 章实体状态跟踪完成。"}
    except Exception as exc:
        return _error(f"实体跟踪失败: {exc}")
