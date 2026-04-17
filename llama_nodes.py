import os
import glob
import requests
from .common import (
    encode_image, extract_response, normalize_api_url,
    get_session, stream_chat_completion, friendly_error
)
from .server_manager import start_llama_server, kill_server

def find_model_files(folder_path):
    """在文件夹中查找 .gguf 模型和可选的 mmproj 文件"""
    if not os.path.isdir(folder_path):
        return None, None
    gguf_files = glob.glob(os.path.join(folder_path, "*.gguf"))
    if not gguf_files:
        return None, None
    
    model_file = None
    mmproj_file = None
    for f in gguf_files:
        basename = os.path.basename(f).lower()
        if "mmproj" in basename:
            mmproj_file = f
        else:
            model_file = f
    
    # 如果没找到 mmproj，尝试在同目录查找
    if mmproj_file is None and model_file is not None:
        base_dir = os.path.dirname(model_file)
        candidates = glob.glob(os.path.join(base_dir, "*mmproj*.gguf"))
        if candidates:
            mmproj_file = candidates[0]
    
    return model_file, mmproj_file


class LLMExternalServerAuto:
    """自动扫描文件夹加载外部 LLM 服务"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_folder": ("STRING", {"default": " ", "tooltip": "包含 .gguf 模型文件的文件夹路径（必填）"}),
                "port": ("INT", {"default": 8080, "min": 1024, "max": 65535}),
                "gpu_layers": ("INT", {"default": -1, "min": -1, "max": 99, "tooltip": "-1 为自动全显存"}),
                "ctx_size": ("INT", {"default": 4096, "min": 512, "max": 131072}),
                "timeout": ("INT", {"default": 180, "min": 30, "max": 900, "step": 10, "tooltip": "API 请求超时时间（秒）"}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256, "tooltip": "生成的最大 token 数"}),
                "force_reload": ("BOOLEAN", {"default": False, "tooltip": "强制重启服务（更换模型时勾选）"}),
            },
            "optional": {
                "exe_path": ("STRING", {"default": r"F:\AItools\LLM\llama\llama-server.exe", "tooltip": "llama-server.exe 路径，请修改为实际路径"}),
                "mmproj_path": ("STRING", {"default": " ", "tooltip": "可选：手动指定 mmproj 文件路径（若自动检测失败）"}),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("api_url", "model_name", "timeout", "max_tokens")
    FUNCTION = "start_server"
    CATEGORY = "LLM_External"

    def start_server(self, model_folder, port=8080, gpu_layers=-1, ctx_size=4096, 
                     timeout=180, max_tokens=4096, force_reload=False, exe_path=" ", mmproj_path=" "):
        if not model_folder or not model_folder.strip():
            return ("错误：请填写模型文件夹路径", " ", timeout, max_tokens)
        
        model_file, auto_mmproj = find_model_files(model_folder)
        if model_file is None:
            return (f"错误：在文件夹 {model_folder} 中未找到 .gguf 模型文件", " ", timeout, max_tokens)
        
        final_mmproj = mmproj_path if mmproj_path and mmproj_path.strip() else (auto_mmproj or " ")
        api_url, model_name, err = start_llama_server(exe_path, model_file, final_mmproj, port, gpu_layers, ctx_size, force_reload)
        
        if err:
            return (err, " ", timeout, max_tokens)
        return (api_url, model_name, timeout, max_tokens)


class LLMExternalServer:
    """手动指定路径加载外部 LLM 服务"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_path": ("STRING", {"default": " ", "tooltip": ".gguf 模型文件的完整路径（必填）"}),
                "mmproj_path": ("STRING", {"default": " ", "tooltip": "如果是 Llava 模型需要填 mmproj 路径，Qwen2-VL 留空即可"}),
                "port": ("INT", {"default": 8080, "min": 1024, "max": 65535}),
                "gpu_layers": ("INT", {"default": -1, "min": -1, "max": 99, "tooltip": "-1 为自动全显存"}),
                "ctx_size": ("INT", {"default": 4096, "min": 512, "max": 131072}),
                "timeout": ("INT", {"default": 180, "min": 30, "max": 900, "step": 10}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256}),
                "force_reload": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "exe_path": ("STRING", {"default": r"F:\AItools\LLM\llama\llama-server.exe", "tooltip": "llama-server.exe 路径，请修改为实际路径"}),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("api_url", "model_name", "timeout", "max_tokens")
    FUNCTION = "start_server"
    CATEGORY = "LLM_External"

    def start_server(self, model_path, mmproj_path, port=8080, gpu_layers=-1, ctx_size=4096, 
                     timeout=180, max_tokens=4096, force_reload=False, exe_path=""):
        if not model_path or not os.path.exists(model_path):
            return (f"错误：模型文件不存在：{model_path}", "", timeout, max_tokens)
        
        api_url, model_name, err = start_llama_server(exe_path, model_path, mmproj_path, port, gpu_layers, ctx_size, force_reload)
        if err:
            return (err, "", timeout, max_tokens)
        return (api_url, model_name, timeout, max_tokens)


class LLMExternalKiller:
    """杀死外部 LLM 服务进程"""
    
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
        result = kill_server(api_url, kill_all)
        print(f"[LLMExternalKiller] {result}")
        return {}


class LLMExternalImageToPrompt:
    """使用多模态模型反推图像提示词"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:8080/v1"}),
                "model_name": ("STRING", {"default": " "}),
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
                full_text = " "
                print("[LLM 流式输出开始]")
                for token in stream_chat_completion(api_url, payload, timeout):
                    print(token, end="", flush=True)
                    full_text += token
                print("\n[LLM 流式输出结束]")
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


class LLMExternalTextChat:
    """纯文本对话生成提示词"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:8080/v1"}),
                "model_name": ("STRING", {"default": " "}),
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
                full_text = " "
                print("[LLM 流式输出开始]")
                for token in stream_chat_completion(api_url, payload, timeout):
                    print(token, end="", flush=True)
                    full_text += token
                print("\n[LLM 流式输出结束]")
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