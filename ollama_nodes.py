import requests
from .common import encode_image, extract_response, normalize_api_url

class OllamaServer:
    """Ollama 连接检查（不启动进程，只验证连接）"""
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
            r = requests.get(test_url, timeout=5)
            if r.status_code == 200:
                print(f"[Ollama] 连接成功，模型 {model_name} 可用")
                return (api_url, model_name, timeout, max_tokens)
            else:
                return (f"ERROR: Ollama 服务响应异常 {r.status_code}", "", timeout, max_tokens)
        except Exception as e:
            return (f"ERROR: 无法连接 Ollama ({e})", "", timeout, max_tokens)


class OllamaImageToPrompt:
    """图像反推提示词（Ollama 后端）"""
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
            },
            "optional": {
                "gpu_layers": ("INT", {"default": -1, "min": -1, "max": 99, "tooltip": "Ollama 下此参数无效，保留仅为兼容"}),
            }
        }
    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "LLM_External"

    def generate(self, api_url, model_name, image, prompt, temperature, timeout, max_tokens, gpu_layers=-1):
        api_url = normalize_api_url(api_url)
        if api_url.startswith("ERROR"):
            return (api_url,)
        payload = {
            "model": model_name,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image(image)}"}}
                ]
            }],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        try:
            res = requests.post(f"{api_url}/chat/completions", json=payload, timeout=timeout)
            res.raise_for_status()
            msg = res.json()["choices"][0]["message"]
            text, warn = extract_response(msg)
            if warn:
                return (f"[警告] {warn}",)
            return (text,)
        except Exception as e:
            return (f"请求失败: {e}",)


class OllamaTextChat:
    """纯文本对话（Ollama 后端）"""
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
            },
            "optional": {
                "gpu_layers": ("INT", {"default": -1, "min": -1, "max": 99, "tooltip": "Ollama 下此参数无效，保留仅为兼容"}),
            }
        }
    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "LLM_External"

    def generate(self, api_url, model_name, system_prompt, user_prompt, temperature, timeout, max_tokens, gpu_layers=-1):
        api_url = normalize_api_url(api_url)
        if api_url.startswith("ERROR"):
            return (api_url,)
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        try:
            res = requests.post(f"{api_url}/chat/completions", json=payload, timeout=timeout)
            res.raise_for_status()
            msg = res.json()["choices"][0]["message"]
            text, warn = extract_response(msg)
            if warn:
                return (f"[警告] {warn}",)
            return (text,)
        except Exception as e:
            return (f"请求失败: {e}",)