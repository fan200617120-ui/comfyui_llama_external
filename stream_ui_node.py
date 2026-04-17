import json
import time
from server import PromptServer
from .common import get_session, normalize_api_url, friendly_error


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
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",   # 关键：让 ComfyUI 传入节点 ID
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate_stream"
    CATEGORY = "LLM_External"
    OUTPUT_NODE = True

    def generate_stream(self, api_url, model_name, system_prompt, user_prompt,
                        temperature, timeout, max_tokens, unique_id):  # 接收 unique_id

        api_url = normalize_api_url(api_url)
        if api_url.startswith("ERROR") or api_url.startswith("错误"):
            # 错误时也可以尝试发送一次更新（可选）
            if unique_id:
                PromptServer.instance.send_sync(
                    "llm_stream_update",
                    {"node_id": str(unique_id), "delta": api_url}
                )
            return (api_url,)

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

        full_text = ""
        pending_delta = ""
        last_push_time = 0

        try:
            session = get_session(api_url)

            with session.post(
                f"{api_url}/chat/completions",
                json=payload,
                timeout=timeout,
                stream=True
            ) as resp:

                resp.raise_for_status()

                buffer = ""
                for chunk in resp.iter_content(chunk_size=None):
                    if not chunk:
                        continue

                    buffer += chunk.decode("utf-8", errors="ignore")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)

                        if not line.startswith("data: "):
                            continue

                        data = line[6:].strip()

                        if data == "[DONE]":
                            break

                        try:
                            obj = json.loads(data)
                            delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                            if not delta:
                                continue

                            full_text += delta
                            pending_delta += delta

                            now = time.time()
                            # 节流：累积长度≥6 或 时间间隔>0.05秒 时发送
                            if len(pending_delta) >= 6 or (now - last_push_time > 0.05):
                                if unique_id:
                                    PromptServer.instance.send_sync(
                                        "llm_stream_update",
                                        {
                                            "node_id": str(unique_id),
                                            "delta": pending_delta
                                        }
                                    )
                                pending_delta = ""
                                last_push_time = now

                        except json.JSONDecodeError:
                            continue

            # 发送最后剩余的 delta
            if pending_delta and unique_id:
                PromptServer.instance.send_sync(
                    "llm_stream_update",
                    {"node_id": str(unique_id), "delta": pending_delta}
                )

            return (full_text,)

        except Exception as e:
            err = friendly_error(e, context=api_url)
            if unique_id:
                PromptServer.instance.send_sync(
                    "llm_stream_update",
                    {"node_id": str(unique_id), "delta": f"\n\n[错误] {err}"}
                )
            return (err,)