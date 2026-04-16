import time
from server import PromptServer
from .common import stream_chat_completion, normalize_api_url, friendly_error


class LLMStreamUI:
    """
    LLM 流式输出节点 - UI 版
    文本一边生成一边在节点内实时刷新显示。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:11434/v1"}),
                "model_name": ("STRING", {"default": "llama3.2"}),
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "写一首关于春天的诗",
                    "lines": 2,
                    "display": "内容提示词"
                }),
                "system_prompt": ("STRING", {
                    "multiline": True,
                    "default": "你是一个专业的AI助手。",
                    "lines": 2,
                    "display": "系统提示词"
                }),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1}),
                "max_tokens": ("INT", {"default": 1024, "min": 256, "max": 8192}),
                "timeout": ("INT", {"default": 120, "min": 30, "max": 600}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("final_text",)
    FUNCTION = "run"
    CATEGORY = "LLM_External"
    OUTPUT_NODE = True

    def run(
        self,
        api_url,
        model_name,
        prompt,
        system_prompt,
        temperature,
        max_tokens,
        timeout,
        unique_id,
    ):
        api_url = normalize_api_url(api_url)

        if api_url.startswith("ERROR") or api_url.startswith("错误"):
            PromptServer.instance.send_sync(
                "llm_stream_update",
                {"node_id": unique_id, "text": api_url},
            )
            return (api_url,)

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        full_text = ""
        last_push_time = 0.0
        PUSH_INTERVAL = 0.05

        try:
            for token in stream_chat_completion(api_url, payload, timeout):
                full_text += token

                now = time.time()
                if now - last_push_time >= PUSH_INTERVAL:
                    PromptServer.instance.send_sync(
                        "llm_stream_update",
                        {"node_id": unique_id, "text": full_text},
                    )
                    last_push_time = now

            PromptServer.instance.send_sync(
                "llm_stream_update",
                {"node_id": unique_id, "text": full_text},
            )

            return (full_text,)

        except Exception as e:
            err = friendly_error(e, context=api_url)
            PromptServer.instance.send_sync(
                "llm_stream_update",
                {"node_id": unique_id, "text": f"错误: {err}"},
            )
            return (err,)
