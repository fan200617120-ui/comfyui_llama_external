# stream_image_node.py (20260423)
import json
import time
from urllib.parse import urlparse
from server import PromptServer
from .common import (
    encode_image,
    get_session,
    normalize_api_url,
    friendly_error,
    apply_thinking_mode
)

def _is_valid_api_url(url):
    """检查是否为可请求的 HTTP(S) URL"""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https")


class LLMStreamImageToPrompt:
    """
    多模态流式反推节点（通用 OpenAI Vision API）
    支持 llama.cpp、Ollama、vLLM、LM Studio 等任何兼容 /v1/chat/completions 的后端。
    前端支持流式 Markdown 渲染（需配合 llm_stream.js）
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:11434/v1"}),
                "model_name": ("STRING", {"default": "llava"}),
                "image": ("IMAGE",),
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "请详细描述这张图片，并生成用于AI绘画的高质量中文提示词。",
                    "lines": 4
                }),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0}),
                "timeout": ("INT", {"default": 180}),
                "max_tokens": ("INT", {"default": 4096}),
                "thinking_mode": (["跟随模型默认", "强制关闭思考", "强制开启思考"], {
                    "default": "跟随模型默认",
                    "tooltip": "控制模型的思考模式。对于不支持思考控制的模型，请选择「跟随模型默认」。"
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

    def generate_stream(self, api_url, model_name, image, prompt,
                        temperature, timeout, max_tokens, thinking_mode, unique_id):
        api_url = normalize_api_url(api_url)
        # 替换不可靠的 startswith 检查
        if not _is_valid_api_url(api_url):
            err_msg = f"错误：无效的 API 地址 '{api_url}'，请确保 LLM 服务已启动。"
            if unique_id:
                PromptServer.instance.send_sync(
                    "llm_stream_update",
                    {"node_id": str(unique_id), "delta": err_msg}
                )
            return (err_msg,)

        # 编码图像为 base64
        image_b64 = encode_image(image, format="PNG")

        # 构建 OpenAI Vision 格式的 payload
        payload = {
            "model": model_name,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                ]
            }],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        # 注入思考模式控制（与文本节点一致）
        apply_thinking_mode(payload, model_name, thinking_mode)

        full_text_parts = []
        pending_delta_parts = []
        last_push_time = time.time()
        done_flag = False

        try:
            session = get_session(api_url)
            with session.post(
                f"{api_url}/chat/completions", json=payload, timeout=timeout, stream=True
            ) as resp:
                resp.raise_for_status()

                buffer = ""
                for chunk in resp.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    if done_flag:
                        break

                    buffer += chunk.decode("utf-8", errors="ignore")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)

                        if not line.startswith("data:"):
                            continue

                        data = line[5:].strip() if line.startswith("data: ") else line[5:].strip()

                        if data == "[DONE]":
                            done_flag = True
                            break

                        try:
                            if not data:
                                continue
                            obj = json.loads(data)
                            delta = obj.get("choices", [{}])[0].get("delta", {})
                            # 兼容 reasoning_content 流式输出
                            current_delta = delta.get("content") or delta.get("reasoning_content")
                            if not current_delta:
                                continue

                            full_text_parts.append(current_delta)
                            pending_delta_parts.append(current_delta)

                            now = time.time()
                            # 节流推送：累积 6 字符或间隔超过 50ms
                            if len(pending_delta_parts) >= 6 or (now - last_push_time > 0.05):
                                if unique_id:
                                    PromptServer.instance.send_sync(
                                        "llm_stream_update",
                                        {"node_id": str(unique_id), "delta": "".join(pending_delta_parts)}
                                    )
                                pending_delta_parts.clear()
                                last_push_time = now

                        except json.JSONDecodeError:
                            continue

                    # 内层 while 后检查 done，跳出外层 for
                    if done_flag:
                        break

                # 推送最后剩余部分
                if pending_delta_parts and unique_id:
                    PromptServer.instance.send_sync(
                        "llm_stream_update",
                        {"node_id": str(unique_id), "delta": "".join(pending_delta_parts)}
                    )

            return ("".join(full_text_parts),)

        except Exception as e:
            err = friendly_error(e, context=api_url)
            if unique_id:
                PromptServer.instance.send_sync(
                    "llm_stream_update",
                    {"node_id": str(unique_id), "delta": f"\n\n[错误] {err}"}
                )
            return (err,)