from .common import encode_image, extract_response, normalize_api_url
from .server_manager import start_llama_server, kill_server
import requests
import os
import glob

def find_model_files(folder_path):
    gguf_files = glob.glob(os.path.join(folder_path, "*.gguf"))
    if not gguf_files:
        return None, None
    model_file = None
    mmproj_file = None
    for f in gguf_files:
        if "mmproj" in os.path.basename(f).lower():
            mmproj_file = f
        else:
            model_file = f
    if model_file is None and gguf_files:
        model_file = gguf_files[0]
    return model_file, mmproj_file


class LLMExternalServerAuto:
    """自动扫描模型文件夹启动 llama-server"""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_folder": ("STRING", {"default": r"F:\AItools\LLM\models\qwen3.5_Unsloth", "tooltip": "包含 .gguf 模型文件的文件夹路径"}),
                "port": ("INT", {"default": 8080, "min": 1024, "max": 65535}),
                "gpu_layers": ("INT", {"default": -1, "min": -1, "max": 99, "tooltip": "-1 为自动全显存"}),
                "ctx_size": ("INT", {"default": 4096, "min": 512, "max": 131072}),
                "timeout": ("INT", {"default": 180, "min": 30, "max": 900, "step": 10, "tooltip": "API 请求超时时间（秒）"}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256, "tooltip": "生成的最大 token 数"}),
                "force_reload": ("BOOLEAN", {"default": False, "tooltip": "强制重启服务（更换模型时勾选）"}),
            },
            "optional": {
                "exe_path": ("STRING", {"default": r"F:\AItools\LLM\llama\llama-server.exe", "tooltip": "llama-server.exe 路径"}),
            }
        }
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("api_url", "model_name", "timeout", "max_tokens")
    FUNCTION = "start_server"
    CATEGORY = "LLM_External"

    def start_server(self, model_folder, port=8080, gpu_layers=-1, ctx_size=4096, timeout=180, max_tokens=4096, force_reload=False, exe_path=""):
        model_file, mmproj_file = find_model_files(model_folder)
        if model_file is None:
            return (f"ERROR: 在 {model_folder} 中未找到 .gguf 模型文件", "", timeout, max_tokens)
        api_url, model_name, err = start_llama_server(exe_path, model_file, mmproj_file or "", port, gpu_layers, ctx_size, force_reload)
        if err:
            return (err, "", timeout, max_tokens)
        return (api_url, model_name, timeout, max_tokens)


class LLMExternalServer:
    """手动指定模型路径启动 llama-server"""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_path": ("STRING", {"default": r"F:\你的模型路径\model.gguf", "tooltip": ".gguf 模型文件的完整路径"}),
                "mmproj_path": ("STRING", {"default": "", "tooltip": "如果是 Llava 模型需要填 mmproj 路径，Qwen2-VL 留空即可"}),
                "port": ("INT", {"default": 8080, "min": 1024, "max": 65535}),
                "gpu_layers": ("INT", {"default": -1, "min": -1, "max": 99, "tooltip": "-1 为自动全显存"}),
                "ctx_size": ("INT", {"default": 4096, "min": 512, "max": 131072}),
                "timeout": ("INT", {"default": 180, "min": 30, "max": 900, "step": 10}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256}),
                "force_reload": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "exe_path": ("STRING", {"default": r"F:\AItools\LLM\llama\llama-server.exe"}),
            }
        }
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("api_url", "model_name", "timeout", "max_tokens")
    FUNCTION = "start_server"
    CATEGORY = "LLM_External"

    def start_server(self, model_path, mmproj_path, port=8080, gpu_layers=-1, ctx_size=4096, timeout=180, max_tokens=4096, force_reload=False, exe_path=""):
        api_url, model_name, err = start_llama_server(exe_path, model_path, mmproj_path, port, gpu_layers, ctx_size, force_reload)
        if err:
            return (err, "", timeout, max_tokens)
        return (api_url, model_name, timeout, max_tokens)


class LLMExternalKiller:
    """卸载/杀死外部 LLM 进程"""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:8080/v1"}),
                "kill_all": ("BOOLEAN", {"default": False}),
            }
        }
    RETURN_TYPES = ()
    FUNCTION = "kill"
    CATEGORY = "LLM_External"
    OUTPUT_NODE = True

    def kill(self, api_url, kill_all):
        kill_server(api_url, kill_all)
        return {}


class LLMExternalImageToPrompt:
    """图像反推提示词（llama.cpp 后端）"""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:8080/v1"}),
                "model_name": ("STRING", {"default": ""}),
                "image": ("IMAGE",),
                "prompt": ("STRING", {"default": "请详细描述这张图片，并生成用于AI绘画的高质量中文提示词。", "multiline": True, "lines": 6}),
                "temperature": ("FLOAT", {"default": 0.6, "min": 0.1, "max": 2.0, "step": 0.1}),
                "timeout": ("INT", {"default": 180, "min": 30, "max": 900, "step": 10}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256}),
            },
            "optional": {
                "gpu_layers": ("INT", {"default": -1, "min": -1, "max": 99, "tooltip": "请求级 GPU 层数，-1 表示使用服务端默认值"}),
            }
        }
    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "LLM_External"

    def generate(self, api_url, model_name, image, prompt, temperature, timeout, max_tokens, gpu_layers=-1):
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
        if gpu_layers >= 0:
            payload["n_gpu_layers"] = gpu_layers
            payload["ngl"] = gpu_layers
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


class LLMExternalTextChat:
    """纯文本对话（llama.cpp 后端）"""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:8080/v1"}),
                "model_name": ("STRING", {"default": ""}),
                "system_prompt": ("STRING", {"default": "你是一个专业的AI绘画提示词工程师。", "multiline": True, "lines": 6}),
                "user_prompt": ("STRING", {"default": "请为'赛博朋克风格的小猫'写一段提示词。", "multiline": True, "lines": 4}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.1, "max": 2.0, "step": 0.1}),
                "timeout": ("INT", {"default": 120, "min": 30, "max": 600, "step": 10}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256}),
            },
            "optional": {
                "gpu_layers": ("INT", {"default": -1, "min": -1, "max": 99, "tooltip": "请求级 GPU 层数，-1 表示使用服务端默认值"}),
            }
        }
    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "LLM_External"

    def generate(self, api_url, model_name, system_prompt, user_prompt, temperature, timeout, max_tokens, gpu_layers=-1):
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
        if gpu_layers >= 0:
            payload["n_gpu_layers"] = gpu_layers
            payload["ngl"] = gpu_layers
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