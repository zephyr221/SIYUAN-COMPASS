from __future__ import annotations

import httpx


def build_llm_timeout(seconds: float) -> httpx.Timeout:
    """Allow slow model reads without allowing slow connection setup."""
    read_timeout = max(seconds, 1)
    return httpx.Timeout(
        connect=min(read_timeout, 10),
        read=read_timeout,
        write=min(read_timeout, 30),
        pool=min(read_timeout, 30),
    )


def describe_llm_transport_error(
    provider_name: str,
    timeout_seconds: float,
    error: httpx.RequestError,
) -> str:
    if isinstance(error, httpx.TimeoutException):
        return (
            f"{provider_name} API 在 {timeout_seconds:g} 秒内未返回数据，"
            "已填写内容仍会保留，请稍后重试。"
        )
    return f"{provider_name} API 网络连接失败：{type(error).__name__}"
