import time
from server import PromptServer
from .common import (
    normalize_api_url,
    friendly_error,
    apply_thinking_mode,
    encode_image,
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


class LLMStreamImageToPrompt:
    """
    多模态流式反推节点（通用 OpenAI Vision API）
    支持最多 8 张图片输入
    前端支持流式 Markdown 渲染（需配合 llm_stream.js）
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:11434/v1"}),
                "model_name": ("STRING", {"default": "llava"}),
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
                    "tooltip": "控制模型的思考模式。"
                }),
                "reasoning_effort": (["无", "low", "medium", "high", "xhigh"], {
                    "default": "无",
                    "tooltip": "推理强度（仅 Qwen3.8 等模型支持）"
                }),
                "max_side": ("INT", {
                    "default": 1024,
                    "min": 128,
                    "max": 4096,
                    "step": 64,
                    "tooltip": "输入图片最大边长，超过则等比缩放"
                }),
                "auto_unload": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "生成后自动卸载该模型（杀死对应端口进程，释放显存）"
                }),
            },
            "optional": {
                "image1": ("IMAGE",),
                "image2": ("IMAGE",),
                "image3": ("IMAGE",),
                "image4": ("IMAGE",),
                "image5": ("IMAGE",),
                "image6": ("IMAGE",),
                "image7": ("IMAGE",),
                "image8": ("IMAGE",),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate_stream"
    CATEGORY = "LLM_External"
    OUTPUT_NODE = True

    def generate_stream(self, api_url, model_name, prompt, temperature, timeout, max_tokens,
                        thinking_mode, reasoning_effort="无", max_side=1024, auto_unload=False,
                        image1=None, image2=None, image3=None, image4=None,
                        image5=None, image6=None, image7=None, image8=None,
                        unique_id=None):
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
        try:
            max_side = int(max_side)
        except (TypeError, ValueError):
            max_side = 1024

        api_url = normalize_api_url(api_url)
        if api_url.startswith("ERROR") or api_url.startswith("错误"):
            _push(unique_id, delta=api_url, reset=True)
            return (api_url,)

        # 修复 #1：重置前端显示
        _push(unique_id, reset=True)

        # 收集所有图片
        images = [img for img in (image1, image2, image3, image4, image5, image6, image7, image8) if img is not None]

        if not images:
            err_msg = "错误：未提供任何图片输入。"
            _push(unique_id, delta=f"\n\n[错误] {err_msg}")
            return (err_msg,)

        # 构建多模态消息内容
        user_content = [{"type": "text", "text": prompt}]
        for img in images:
            img_b64 = encode_image(img, format="PNG", max_side=max_side)
            if not img_b64:
                continue
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}"}
            })

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": user_content}],
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
                warn = "[警告] 模型未返回任何内容。可能原因：max_tokens 过小、服务端返回空回复、或流中途出错。"
                print(f"[LLM Stream Image] {warn}")
                _push(unique_id, delta=f"\n\n{warn}")
                final_text = warn

            if auto_unload:
                msg, err = unload_by_api_url(api_url)
                if err:
                    print(f"[LLM Stream Image] 卸载失败: {err}")
                else:
                    print(f"[LLM Stream Image] {msg}")

            return (final_text,)

        except Exception as e:
            err = friendly_error(e, context=api_url)
            _push(unique_id, delta=f"\n\n[错误] {err}")
            return (err,)