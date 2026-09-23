"""OpenAI Responses HTTP 适配器。默认无网络；不执行模型返回的任意工具。"""

import json
import httpx
from app.agents.contracts import ModelTurn, ProviderError, ToolCall


class OpenAIResponsesProvider:
    def __init__(self, key, *, api_url, transport=None):
        self._key = key
        from app.core.config import Settings

        self._api_url = Settings.validate_agent_api_url(api_url)
        if not self._api_url:
            raise ValueError("AGENT_API_URL 未配置")
        self._transport = transport

    async def complete(self, *, model, instructions, items, tools, max_output_tokens, timeout):
        try:
            # 地址仅由服务端配置；无隐式重试、无客户端可控地址、无重定向。
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=False, transport=self._transport,
            ) as client:
                async with client.stream(
                    "POST",
                    self._api_url,
                    headers={"Authorization": "Bearer " + self._key.get_secret_value()},
                    json={
                        "model": model, "instructions": instructions, "input": items,
                        "tools": tools, "max_output_tokens": max_output_tokens,
                        "parallel_tool_calls": False, "store": False,
                    },
                ) as response:
                    response.raise_for_status()
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 1024 * 1024:
                            raise ProviderError("provider_output_too_large")
                    data = json.loads(content)
            if data.get("status") != "completed":
                raise ProviderError("provider_incomplete")
            calls, texts = [], []
            for item in data.get("output", []):
                if item.get("type") == "function_call":
                    calls.append(ToolCall(item["call_id"], item["name"], item["arguments"]))
                elif item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "refusal":
                            raise ProviderError("provider_refused")
                        if content.get("type") == "output_text":
                            texts.append(content["text"])
            usage = data["usage"]
            return ModelTurn(
                text="\n".join(texts), calls=calls,
                input_tokens=int(usage["input_tokens"]), output_tokens=int(usage["output_tokens"]),
            )
        except ProviderError:
            raise
        except httpx.TimeoutException:
            raise ProviderError("provider_timeout") from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ProviderError("provider_unavailable") from None


class DeepSeekChatProvider(OpenAIResponsesProvider):
    """Chat Completions adapter; non-thinking avoids retaining hidden reasoning."""

    async def complete(self, *, model, instructions, items, tools, max_output_tokens, timeout):
        try:
            messages = [{"role": "system", "content": instructions}]
            for item in items:
                kind = item.get("type")
                if kind == "function_call":
                    messages.append({"role": "assistant", "content": None, "tool_calls": [{
                        "id": item["call_id"], "type": "function", "function": {
                            "name": item["name"], "arguments": item["arguments"],
                        },
                    }]})
                elif kind == "function_call_output":
                    messages.append({"role": "tool", "tool_call_id": item["call_id"], "content": item["output"]})
                elif item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str):
                    messages.append({"role": item["role"], "content": item["content"]})
                else:
                    raise ProviderError("provider_invalid_output")
            body = {"model": model, "messages": messages, "stream": False,
                    "max_tokens": max_output_tokens, "thinking": {"type": "disabled"}}
            if tools:
                # Stable Chat endpoint doesn't require beta strict mode; backend validates every call.
                body["tools"] = [{"type": "function", "function": {
                    "name": tool["name"], "description": tool["description"],
                    "parameters": tool["parameters"],
                }} for tool in tools]
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, transport=self._transport) as client:
                async with client.stream("POST", self._api_url,
                                         headers={"Authorization": "Bearer " + self._key.get_secret_value()},
                                         json=body) as response:
                    if response.status_code in {401, 403}:
                        raise ProviderError("provider_auth_failed")
                    if response.status_code == 429:
                        raise ProviderError("provider_rate_limited")
                    response.raise_for_status()
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 1024 * 1024:
                            raise ProviderError("provider_output_too_large")
                    data = json.loads(content)
            if len(data["choices"]) != 1:
                raise ProviderError("provider_invalid_output")
            choice = data["choices"][0]
            if choice["finish_reason"] == "content_filter":
                raise ProviderError("provider_refused")
            if choice["finish_reason"] not in {"stop", "tool_calls"}:
                raise ProviderError("provider_incomplete")
            message = choice["message"]
            calls = [ToolCall(call["id"], call["function"]["name"], call["function"]["arguments"])
                     for call in message.get("tool_calls", [])]
            if bool(calls) != (choice["finish_reason"] == "tool_calls"):
                raise ProviderError("provider_invalid_output")
            usage = data["usage"]
            return ModelTurn(text=message.get("content") or "", calls=calls,
                             input_tokens=int(usage["prompt_tokens"]), output_tokens=int(usage["completion_tokens"]))
        except ProviderError:
            raise
        except httpx.TimeoutException:
            raise ProviderError("provider_timeout") from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
            raise ProviderError("provider_unavailable") from None
