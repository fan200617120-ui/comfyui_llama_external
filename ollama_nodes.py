import requests
from .common import (
    encode_image, extract_response, normalize_api_url,
    get_session, stream_chat_completion, friendly_error
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
        api_url = normalize_api_url(api_url)
        test_url = f"{api_url}/models"
        try:
            session = get_session(api_url)
            r = session.get(test_url, timeout=5)
            if r.status_code != 200:
                return (f"错误：Ollama 服务响应异常 ({r.status_code})", "", timeout, max_tokens)
            models_data = r.json()
            available_models = [m["id"] for m in models_data.get("data", [])]
            if model_name not in available_models:
                return (f"错误：模型 '{model_name}' 未找到。\n可用模型: {', '.join(available_models) if available_models else '无'}\n提示：请先运行 'ollama pull {model_name}' 下载模型。", "", timeout, max_tokens)
        except requests.exceptions.ConnectionError:
            return ("错误：无法连接 Ollama。\n请确认 Ollama 已启动 (ollama serve) 且地址正确。", "", timeout, max_tokens)
        except Exception as e:
            return (friendly_error(e, context=api_url), "", timeout, max_tokens)
        print(f"[Ollama] 连接成功，模型 {model_name} 可用")
        return (api_url, model_name, timeout, max_tokens)

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
            }
        }
    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "LLM_External"

    def generate(self, api_url, model_name, image, prompt, temperature, timeout, max_tokens, stream):
        api_url = normalize_api_url(api_url)
        if api_url.startswith("ERROR") or api_url.startswith("错误"):
            return (api_url,)
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
        try:
            if stream:
                full_text = ""
                print("[Ollama 流式输出开始]")
                for token in stream_chat_completion(api_url, payload, timeout):
                    print(token, end="", flush=True)
                    full_text += token
                print("\n[Ollama 流式输出结束]")
                return (full_text,)
            else:
                session = get_session(api_url)
                resp = session.post(f"{api_url}/chat/completions", json=payload, timeout=timeout)
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]
                text, warn = extract_response(msg)
                if warn:
                    return (f"[注意] {warn}\n\n{text}",)
                return (text,)
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
            }
        }
    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "LLM_External"

    def generate(self, api_url, model_name, system_prompt, user_prompt, temperature, timeout, max_tokens, stream):
        api_url = normalize_api_url(api_url)
        if api_url.startswith("ERROR") or api_url.startswith("错误"):
            return (api_url,)
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
        try:
            if stream:
                full_text = ""
                print("[Ollama 流式输出开始]")
                for token in stream_chat_completion(api_url, payload, timeout):
                    print(token, end="", flush=True)
                    full_text += token
                print("\n[Ollama 流式输出结束]")
                return (full_text,)
            else:
                session = get_session(api_url)
                resp = session.post(f"{api_url}/chat/completions", json=payload, timeout=timeout)
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]
                text, warn = extract_response(msg)
                if warn:
                    return (f"[注意] {warn}\n\n{text}",)
                return (text,)
        except Exception as e:
            return (friendly_error(e, context=api_url),)
