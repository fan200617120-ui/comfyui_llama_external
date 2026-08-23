import os
import glob
import requests
import shutil
import folder_paths
from .common import (
    encode_image,
    get_session,
    stream_chat_completion,
    friendly_error,
    apply_thinking_mode,
    execute_non_stream_chat,
    get_gguf_files,
    get_mmproj_files,
    parse_kv_cache_type,
    get_llm_folder
)
from .server_manager import start_llama_server, kill_server, unload_by_api_url


class LLMExternalServerAuto:
    """自动扫描文件夹加载外部 LLM 服务（下拉选择模型）"""

    @classmethod
    def INPUT_TYPES(cls):
        model_files = get_gguf_files()
        if not model_files:
            model_files = ["（请将模型放入 models/LLM 文件夹）"]
        mmproj_files = ["无"] + get_mmproj_files()
        
        return {
            "required": {
                "model_file": (model_files, {"default": model_files[0] if model_files else "（请将模型放入 models/LLM 文件夹）", "tooltip": "选择主模型 .gguf 文件"}),
                "mmproj_file": (mmproj_files, {"default": "无", "tooltip": "多模态模型需要 mmproj 文件（可选）"}),
                "port": ("INT", {"default": 8080, "min": 1024, "max": 65535}),
                "gpu_layers": ("INT", {"default": -1, "min": -1, "max": 99, "tooltip": "-1 为自动全显存"}),
                "ctx_size": ("INT", {"default": 4096, "min": 512, "max": 131072, "step": 256, "tooltip": "上下文长度"}),
                "cache_type_k": (["默认(F16)", "q8_0"], {"default": "默认(F16)", "tooltip": "KV 缓存 K 类型"}),
                "cache_type_v": (["默认(F16)", "q8_0"], {"default": "默认(F16)", "tooltip": "KV 缓存 V 类型"}),
                "cpu_moe": ("BOOLEAN", {"default": False, "tooltip": "MoE 专家全部放到 CPU"}),
                "n_cpu_moe": ("INT", {"default": 0, "min": 0, "max": 256, "step": 1, "tooltip": "前 N 层专家放到 CPU"}),
                "timeout": ("INT", {"default": 180, "min": 30, "max": 900, "step": 10}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256}),
                "force_reload": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "exe_path": ("STRING", {"default": "", "tooltip": "llama-server.exe 路径，留空则自动查找 PATH"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("api_url", "model_name", "timeout", "max_tokens")
    FUNCTION = "start_server"
    CATEGORY = "LLM_External"

    def start_server(self, model_file, mmproj_file, port, gpu_layers, ctx_size,
                     cache_type_k, cache_type_v, cpu_moe, n_cpu_moe,
                     timeout, max_tokens, force_reload, exe_path=""):
        # 防御性类型转换
        try:
            port = int(port)
        except Exception:
            port = 8080
        try:
            gpu_layers = int(gpu_layers)
        except Exception:
            gpu_layers = -1
        try:
            ctx_size = int(ctx_size)
        except Exception:
            ctx_size = 4096
        try:
            n_cpu_moe = int(n_cpu_moe)
        except Exception:
            n_cpu_moe = 0
        try:
            timeout = int(timeout)
        except Exception:
            timeout = 180
        try:
            max_tokens = int(max_tokens)
        except Exception:
            max_tokens = 4096

        # 如果 exe_path 为空，尝试从 PATH 查找
        if not exe_path or not exe_path.strip():
            exe_path = shutil.which("llama-server")
            if not exe_path:
                return ("错误：找不到 llama-server，请安装 llama.cpp 或将路径填入 exe_path", "", timeout, max_tokens)
        elif not os.path.exists(exe_path):
            return (f"错误：找不到 llama-server 可执行文件\n{exe_path}", "", timeout, max_tokens)

        model_folder = get_llm_folder()
        if not model_folder:
            return ("错误：无法找到 models/LLM 文件夹，请确保 ComfyUI 已正确配置。", "", timeout, max_tokens)
        
        if not model_file or model_file == "（请将模型放入 models/LLM 文件夹）":
            return ("错误：请选择有效的模型文件", "", timeout, max_tokens)
        full_model_path = os.path.join(model_folder, model_file)
        if not os.path.exists(full_model_path):
            return (f"错误：模型文件不存在：{full_model_path}", "", timeout, max_tokens)
        
        final_mmproj = ""
        if mmproj_file and mmproj_file != "无":
            final_mmproj = os.path.join(model_folder, mmproj_file)
            if not os.path.exists(final_mmproj):
                return (f"错误：mmproj 文件不存在：{final_mmproj}", "", timeout, max_tokens)
        
        cache_k = parse_kv_cache_type(cache_type_k)
        cache_v = parse_kv_cache_type(cache_type_v)
        
        api_url, model_name, err = start_llama_server(
            exe_path, full_model_path, final_mmproj, port,
            gpu_layers, ctx_size, force_reload,
            cache_type_k=cache_k, cache_type_v=cache_v,
            cpu_moe=cpu_moe, n_cpu_moe=n_cpu_moe
        )
        if err:
            return (err, "", timeout, max_tokens)
        return (api_url, model_name, timeout, max_tokens)


class LLMExternalServer:
    """手动指定路径加载外部 LLM 服务（文本输入路径）"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_path": ("STRING", {"default": "", "tooltip": ".gguf 模型文件的完整路径（必填）"}),
                "mmproj_path": ("STRING", {"default": "", "tooltip": "如果是多模态模型需要填 mmproj 路径，否则留空"}),
                "port": ("INT", {"default": 8080, "min": 1024, "max": 65535}),
                "gpu_layers": ("INT", {"default": -1, "min": -1, "max": 99, "tooltip": "-1 为自动全显存"}),
                "ctx_size": ("INT", {"default": 4096, "min": 512, "max": 131072, "step": 256}),
                "cache_type_k": (["默认(F16)", "q8_0"], {"default": "默认(F16)"}),
                "cache_type_v": (["默认(F16)", "q8_0"], {"default": "默认(F16)"}),
                "cpu_moe": ("BOOLEAN", {"default": False}),
                "n_cpu_moe": ("INT", {"default": 0, "min": 0, "max": 256, "step": 1}),
                "timeout": ("INT", {"default": 180, "min": 30, "max": 900, "step": 10}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256}),
                "force_reload": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "exe_path": ("STRING", {"default": "", "tooltip": "llama-server.exe 路径，留空则自动查找 PATH"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("api_url", "model_name", "timeout", "max_tokens")
    FUNCTION = "start_server"
    CATEGORY = "LLM_External"

    def start_server(self, model_path, mmproj_path, port, gpu_layers, ctx_size,
                     cache_type_k, cache_type_v, cpu_moe, n_cpu_moe,
                     timeout, max_tokens, force_reload, exe_path=""):
        try:
            port = int(port)
        except Exception:
            port = 8080
        try:
            gpu_layers = int(gpu_layers)
        except Exception:
            gpu_layers = -1
        try:
            ctx_size = int(ctx_size)
        except Exception:
            ctx_size = 4096
        try:
            n_cpu_moe = int(n_cpu_moe)
        except Exception:
            n_cpu_moe = 0
        try:
            timeout = int(timeout)
        except Exception:
            timeout = 180
        try:
            max_tokens = int(max_tokens)
        except Exception:
            max_tokens = 4096

        if not exe_path or not exe_path.strip():
            exe_path = shutil.which("llama-server")
            if not exe_path:
                return ("错误：找不到 llama-server，请安装 llama.cpp 或将路径填入 exe_path", "", timeout, max_tokens)
        elif not os.path.exists(exe_path):
            return (f"错误：找不到 llama-server 可执行文件\n{exe_path}", "", timeout, max_tokens)

        if not model_path or not os.path.exists(model_path):
            return (f"错误：模型文件不存在：{model_path}", "", timeout, max_tokens)
        final_mmproj = mmproj_path.strip() if mmproj_path and mmproj_path.strip() else ""
        cache_k = parse_kv_cache_type(cache_type_k)
        cache_v = parse_kv_cache_type(cache_type_v)
        api_url, model_name, err = start_llama_server(
            exe_path, model_path, final_mmproj, port,
            gpu_layers, ctx_size, force_reload,
            cache_type_k=cache_k, cache_type_v=cache_v,
            cpu_moe=cpu_moe, n_cpu_moe=n_cpu_moe
        )
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
    RETURN_NAMES = ()
    FUNCTION = "kill"
    CATEGORY = "LLM_External"
    OUTPUT_NODE = True

    def kill(self, api_url, kill_all):
        result = kill_server(api_url, kill_all)
        print(f"[LLMExternalKiller] {result}")
        return ()


class LLMExternalImageToPrompt:
    """使用多模态模型反推图像提示词（支持多图输入、最大边长缩放、自动卸载）"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:8080/v1"}),
                "model_name": ("STRING", {"default": ""}),
                "prompt": ("STRING", {"default": "请详细描述这张图片，并生成用于AI绘画的高质量中文提示词。", "multiline": True, "lines": 6}),
                "temperature": ("FLOAT", {"default": 0.6, "min": 0.1, "max": 2.0, "step": 0.1}),
                "timeout": ("INT", {"default": 180, "min": 30, "max": 900, "step": 10}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 16384, "step": 256}),
                "stream": ("BOOLEAN", {"default": False, "tooltip": "是否启用流式输出（实时打印token）"}),
                "thinking_mode": (["跟随模型默认", "强制关闭思考", "强制开启思考"], {"default": "跟随模型默认"}),
                "reasoning_effort": (["无", "low", "medium", "high", "xhigh"], {"default": "无", "tooltip": "推理强度（仅 Qwen3.8 等支持）"}),
                "max_side": ("INT", {"default": 1024, "min": 128, "max": 4096, "step": 64, "tooltip": "输入图片最大边长，超过则等比缩放"}),
                "auto_unload": ("BOOLEAN", {"default": False, "tooltip": "生成后自动卸载该模型"}),
            },
            "optional": {
                "image": ("IMAGE",),
                "image2": ("IMAGE",),
                "image3": ("IMAGE",),
                "image4": ("IMAGE",),
                "image5": ("IMAGE",),
                "image6": ("IMAGE",),
                "image7": ("IMAGE",),
                "image8": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "LLM_External"

    def generate(self, api_url, model_name, prompt, temperature, timeout, max_tokens, stream,
                 thinking_mode, reasoning_effort="无", max_side=1024, auto_unload=False, **kwargs):
        try:
            temperature = float(temperature)
        except Exception:
            temperature = 0.6
        try:
            timeout = int(timeout)
        except Exception:
            timeout = 180
        try:
            max_tokens = int(max_tokens)
        except Exception:
            max_tokens = 4096
        try:
            max_side = int(max_side)
        except Exception:
            max_side = 1024

        # 修复 #7：统一图片收集
        IMAGE_KEYS = ("image", "image2", "image3", "image4",
                      "image5", "image6", "image7", "image8")
        images = []
        for key in IMAGE_KEYS:
            img = kwargs.get(key)
            if img is not None:
                images.append(img)
        
        if not images:
            return ("错误：未提供任何图片输入。",)
        
        content = [{"type": "text", "text": prompt}]
        for img in images:
            img_b64 = encode_image(img, format="PNG", max_side=max_side)
            if not img_b64:
                continue
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}})
        
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        effort = reasoning_effort if reasoning_effort != "无" else None
        apply_thinking_mode(payload, model_name, thinking_mode, reasoning_effort=effort)
        
        try:
            if stream:
                full_text_parts = []
                print("[LLM 流式输出开始]")
                for token in stream_chat_completion(api_url, payload, timeout):
                    print(token, end="", flush=True)
                    full_text_parts.append(token)
                print("\n[LLM 流式输出结束]")
                result = "".join(full_text_parts)
            else:
                result, success = execute_non_stream_chat(api_url, payload, timeout)
                if not success:
                    return (result,)
            
            if not result or not result.strip():
                result = "[提示] 模型未返回任何内容。"
            
            if auto_unload:
                msg, err = unload_by_api_url(api_url)
                if err:
                    print(f"[LLM External] 卸载失败: {err}")
                else:
                    print(f"[LLM External] {msg}")
            
            return (result,)
        except Exception as e:
            return (friendly_error(e, context=api_url),)


class LLMExternalTextChat:
    """纯文本对话生成提示词（支持推理强度、自动卸载）"""

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
                "stream": ("BOOLEAN", {"default": False, "tooltip": "是否启用流式输出"}),
                "thinking_mode": (["跟随模型默认", "强制关闭思考", "强制开启思考"], {"default": "跟随模型默认"}),
                "reasoning_effort": (["无", "low", "medium", "high", "xhigh"], {"default": "无", "tooltip": "推理强度（仅 Qwen3.8 等模型支持）"}),
                "auto_unload": ("BOOLEAN", {"default": False, "tooltip": "生成后自动卸载该模型"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "LLM_External"

    def generate(self, api_url, model_name, system_prompt, user_prompt, temperature, timeout, max_tokens, stream, thinking_mode, reasoning_effort="无", auto_unload=False):
        try:
            temperature = float(temperature)
        except Exception:
            temperature = 0.7
        try:
            timeout = int(timeout)
        except Exception:
            timeout = 120
        try:
            max_tokens = int(max_tokens)
        except Exception:
            max_tokens = 4096

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
        effort = reasoning_effort if reasoning_effort != "无" else None
        apply_thinking_mode(payload, model_name, thinking_mode, reasoning_effort=effort)

        try:
            if stream:
                full_text_parts = []
                print("[LLM 流式输出开始]")
                try:
                    for token in stream_chat_completion(api_url, payload, timeout):
                        print(token, end="", flush=True)
                        full_text_parts.append(token)
                except (requests.exceptions.RequestException, ValueError) as e:
                    error_msg = f"\n[流式处理错误] {str(e)}"
                    print(error_msg, end="")
                    full_text_parts.append(error_msg)
                print("\n[LLM 流式输出结束]")
                result = "".join(full_text_parts)
            else:
                result, success = execute_non_stream_chat(api_url, payload, timeout)
                if not success:
                    return (result,)
            
            if not result or not result.strip():
                result = "[提示] 模型未返回任何内容。"
            
            if auto_unload:
                msg, err = unload_by_api_url(api_url)
                if err:
                    print(f"[LLM External] 卸载失败: {err}")
                else:
                    print(f"[LLM External] {msg}")
            
            return (result,)
        except Exception as e:
            return (friendly_error(e, context=api_url),)