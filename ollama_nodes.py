import requests
from .common import (
    encode_image,
    normalize_api_url,
    get_session,
    stream_chat_completion,
    friendly_error,
    apply_thinking_mode,
    execute_non_stream_chat
)

class OllamaServer:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:11434", "tooltip": "Ollama 地址，会自动补全 /v1"}),
                "model_name": ("STRING", {"default": "llava", "tooltip": "Ollama 中的多模态模型名称（如 llava, bakllava, moondream）"}),
                "timeout": ("INT", {"default": 180, "min": 30, "max": 900, "step": 10}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256}),
            }
        }
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("api_url", "model_name", "timeout", "max_tokens")
    FUNCTION = "check"
    CATEGORY = "LLM_External"

    def check(self, api_url, model_name, timeout, max_tokens):
        base_url = api_url.rstrip('/')
        if base_url.endswith('/v1'):
            base_url = base_url[:-3]
        tags_url = f"{base_url}/api/tags"
        try:
            session = get_session(base_url)
            r = session.get(tags_url, timeout=5)
            if r.status_code != 200:
                return (f"错误：Ollama 服务响应异常 ({r.status_code})", "", timeout, max_tokens)
            data = r.json()
            models = data.get("models", [])
            available_models = [m["name"] for m in models]
            if model_name not in available_models:
                return (f"错误：模型 '{model_name}' 未找到。\n可用模型: {', '.join(available_models) if available_models else '无'}\n提示：请先运行 'ollama pull {model_name}' 下载模型。", "", timeout, max_tokens)
        except requests.exceptions.ConnectionError:
            return ("错误：无法连接 Ollama。\n请确认 Ollama 已启动 (ollama serve) 且地址正确。", "", timeout, max_tokens)
        except (requests.exceptions.RequestException, ValueError) as e:
            return (friendly_error(e, context=api_url), "", timeout, max_tokens)
        print(f"[Ollama] 连接成功，模型 {model_name} 可用")
        normalized = normalize_api_url(api_url)
        return (normalized, model_name, timeout, max_tokens)


class OllamaImageToPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:11434/v1"}),
                "model_name": ("STRING", {"default": "llava"}),
                "image": ("IMAGE",),
                "prompt": ("STRING", {"default": "请详细描述这张图片，并生成用于AI绘画的高质量中文提示词。", "multiline": True, "lines": 6}),
                "temperature": ("FLOAT", {"default": 0.6, "min": 0.1, "max": 2.0, "step": 0.1}),
                "timeout": ("INT", {"default": 180, "min": 30, "max": 900, "step": 10}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256}),
                "stream": ("BOOLEAN", {"default": False, "tooltip": "是否启用流式输出（实时打印token）"}),
                "thinking_mode": (["跟随模型默认", "强制关闭思考", "强制开启思考"], {"default": "跟随模型默认"}),
            }
        }
    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "LLM_External"

    def generate(self, api_url, model_name, image, prompt, temperature, timeout, max_tokens, stream, thinking_mode):
        image_b64 = encode_image(image, format="PNG")
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
            "stream": stream
        }
        apply_thinking_mode(payload, model_name, thinking_mode)

        try:
            if stream:
                full_text_parts = []
                print("[Ollama 流式输出开始]")
                try:
                    for token in stream_chat_completion(api_url, payload, timeout):
                        print(token, end="", flush=True)
                        full_text_parts.append(token)
                except (requests.exceptions.RequestException, ValueError) as e:
                    error_msg = f"\n[流式处理错误] {str(e)}"
                    print(error_msg, end="")
                    full_text_parts.append(error_msg)
                print("\n[Ollama 流式输出结束]")
                return ("".join(full_text_parts),)
            else:
                result, _ = execute_non_stream_chat(api_url, payload, timeout)
                return (result,)
        except Exception as e:
            return (friendly_error(e, context=api_url),)


class OllamaTextChat:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:11434/v1"}),
                "model_name": ("STRING", {"default": "llama3.2-vision"}),
                "system_prompt": ("STRING", {"default": "你是一个专业的AI绘画提示词工程师。", "multiline": True, "lines": 6}),
                "user_prompt": ("STRING", {"default": "请为'赛博朋克风格的小猫'写一段提示词。", "multiline": True, "lines": 4}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.1, "max": 2.0, "step": 0.1}),
                "timeout": ("INT", {"default": 120, "min": 30, "max": 600, "step": 10}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256}),
                "stream": ("BOOLEAN", {"default": False, "tooltip": "是否启用流式输出（实时打印token）"}),
                "thinking_mode": (["跟随模型默认", "强制关闭思考", "强制开启思考"], {"default": "跟随模型默认"}),
            }
        }
    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "LLM_External"

    def generate(self, api_url, model_name, system_prompt, user_prompt, temperature, timeout, max_tokens, stream, thinking_mode):
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        apply_thinking_mode(payload, model_name, thinking_mode)

        try:
            if stream:
                full_text_parts = []
                print("[Ollama 流式输出开始]")
                try:
                    for token in stream_chat_completion(api_url, payload, timeout):
                        print(token, end="", flush=True)
                        full_text_parts.append(token)
                except (requests.exceptions.RequestException, ValueError) as e:
                    error_msg = f"\n[流式处理错误] {str(e)}"
                    print(error_msg, end="")
                    full_text_parts.append(error_msg)
                print("\n[Ollama 流式输出结束]")
                return ("".join(full_text_parts),)
            else:
                result, _ = execute_non_stream_chat(api_url, payload, timeout)
                return (result,)
        except Exception as e:
            return (friendly_error(e, context=api_url),)