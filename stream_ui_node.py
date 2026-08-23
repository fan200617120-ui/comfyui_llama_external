import time

from server import PromptServer

from .common import (
    normalize_api_url,
    friendly_error,
    apply_thinking_mode,
    iter_chat_stream,
)
from .server_manager import unload_by_api_url


def _push(unique_id, delta=None, reset=False):
    """向后端推送流式更新（支持 reset + delta 同一条消息）"""
    if not unique_id:
        return
    payload = {"node_id": str(unique_id)}
    if reset:
        payload["reset"] = True
    if delta:
        payload["delta"] = delta
    PromptServer.instance.send_sync("llm_stream_update", payload)


class LLMStreamUI:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:11434/v1"}),
                "model_name": ("STRING", {"default": "llama3.2"}),
                "system_prompt": ("STRING", {"multiline": True, "default": "You are a helpful AI assistant."}),
                "user_prompt": ("STRING", {"multiline": True, "default": "请开始流式输出..."}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0}),
                "timeout": ("INT", {"default": 180}),
                "max_tokens": ("INT", {"default": 4096}),
                "thinking_mode": (["跟随模型默认", "强制关闭思考", "强制开启思考"], {
                    "default": "跟随模型默认",
                    "tooltip": "控制模型的思考模式。对于不支持思考控制的模型，请选择「跟随模型默认」。"
                }),
                "reasoning_effort": (["无", "low", "medium", "high", "xhigh"], {
                    "default": "无",
                    "tooltip": "推理强度（仅 Qwen3.8 等模型支持）"
                }),
                "auto_unload": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "生成后自动卸载该模型（杀死对应端口进程，释放显存）"
                }),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate_stream"
    CATEGORY = "LLM_External"
    OUTPUT_NODE = True

    def generate_stream(self, api_url, model_name, system_prompt, user_prompt,
                        temperature, timeout, max_tokens, thinking_mode,
                        reasoning_effort="无", auto_unload=False, unique_id=None):
        try:
            temperature = float(temperature)
        except (TypeError, ValueError):
            temperature = 0.7
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = 180
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError):
            max_tokens = 4096

        api_url = normalize_api_url(api_url)
        if api_url.startswith("ERROR") or api_url.startswith("错误"):
            _push(unique_id, delta=api_url, reset=True)
            return (api_url,)

        # 修复 #1：重置前端显示
        _push(unique_id, reset=True)

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        effort = reasoning_effort if reasoning_effort != "无" else None
        apply_thinking_mode(payload, model_name, thinking_mode, reasoning_effort=effort)

        full_text_parts = []
        pending_delta_parts = []
        last_push_time = time.time()

        try:
            for token in iter_chat_stream(api_url, payload, timeout):
                full_text_parts.append(token)
                pending_delta_parts.append(token)

                now = time.time()
                if len(pending_delta_parts) >= 6 or (now - last_push_time) > 0.05:
                    _push(unique_id, delta="".join(pending_delta_parts))
                    pending_delta_parts.clear()
                    last_push_time = now

            if pending_delta_parts:
                _push(unique_id, delta="".join(pending_delta_parts))

            final_text = "".join(full_text_parts)
            if not final_text or not final_text.strip():
                warn = ("[警告] 模型未返回任何内容。可能原因："
                        "max_tokens 过小、服务端返回空回复、或流中途出错。")
                print(f"[LLM Stream UI] {warn}")
                _push(unique_id, delta=f"\n\n{warn}")
                final_text = warn

            if auto_unload:
                msg, err = unload_by_api_url(api_url)
                if err:
                    print(f"[LLM Stream UI] 卸载失败: {err}")
                else:
                    print(f"[LLM Stream UI] {msg}")

            return (final_text,)

        except Exception as e:
            err = friendly_error(e, context=api_url)
            _push(unique_id, delta=f"\n\n[错误] {err}")
            return (err,)