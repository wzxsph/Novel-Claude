"""Lazy Zhipu Batch API client."""

from __future__ import annotations

from zhipuai import ZhipuAI

from utils import config


class BatchConfigurationError(RuntimeError):
    """Raised when a Zhipu-only feature is used without a Zhipu key."""


_client: ZhipuAI | None = None
_client_key: str | None = None


def get_batch_client() -> ZhipuAI:
    global _client, _client_key
    if not config.ZHIPU_API_KEY:
        raise BatchConfigurationError(
            "Batch API 需要 ZHIPU_API_KEY；当 LLM_PROVIDER=zhipu 时也可复用 LLM_API_KEY。"
        )
    if _client is None or _client_key != config.ZHIPU_API_KEY:
        _client = ZhipuAI(api_key=config.ZHIPU_API_KEY)
        _client_key = config.ZHIPU_API_KEY
    return _client


def reset_batch_client() -> None:
    global _client, _client_key
    _client = None
    _client_key = None


def submit_batch_task(
    jsonl_file_path: str,
    endpoint: str = "/v4/chat/completions",
    desc: str = "",
) -> str:
    client = get_batch_client()
    with open(jsonl_file_path, "rb") as handle:
        file_object = client.files.create(file=handle, purpose="batch")
    batch = client.batches.create(
        input_file_id=file_object.id,
        endpoint=endpoint,
        auto_delete_input_file=True,
        metadata={"description": desc},
    )
    return batch.id


def get_batch_status(batch_id: str):
    return get_batch_client().batches.retrieve(batch_id)


def download_batch_results(batch_id: str, output_path: str, error_path: str | None = None):
    client = get_batch_client()
    status = client.batches.retrieve(batch_id)
    if status.status != "completed":
        return False

    if status.output_file_id:
        client.files.content(status.output_file_id).write_to_file(output_path)
        print(f"[Batch] 结果已保存至: {output_path}")
    if status.error_file_id and error_path:
        client.files.content(status.error_file_id).write_to_file(error_path)
        print(f"[Batch] 错误日志已保存至: {error_path}")
    return True
