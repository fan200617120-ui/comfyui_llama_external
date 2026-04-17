import base64
from io import BytesIO
from PIL import Image
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import atexit
import sys
import os
import json

# === 强制设置 Windows 控制台为 UTF-8（无感修复） ===
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except:
        pass

# ------------------- 全局 Session 管理 -------------------
_session_cache = {}

def get_session(base_url, timeout=30):
    """获取带重试机制的 requests Session"""
    if base_url not in _session_cache:
        session = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=10)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        _session_cache[base_url] = session
    return _session_cache[base_url]

def clear_sessions():
    """程序退出时关闭所有 session"""
    for url, session in _session_cache.items():
        try:
            session.close()
        except:
            pass
    _session_cache.clear()

atexit.register(clear_sessions)

# ------------------- 友好错误消息映射 -------------------
FRIENDLY_ERRORS = {
    "ConnectionError": "无法连接到服务。可能原因：\n1. llama-server 或 Ollama 没有启动\n2. 端口被防火墙拦截\n3. 地址填写错误",
    "Timeout": "请求超时。可能原因：\n1. 模型推理太慢（尝试减少上下文长度）\n2. 网络不稳定\n3. 超时设置过短",
    "model_not_found": "模型名称不存在。可能原因：\n1. 模型未下载（Ollama 需先 pull）\n2. 名称拼写错误\n3. 模型文件路径不正确",
    "server_crash": "LLM 服务意外退出。请检查模型兼容性或显存是否不足。",
    "port_conflict": "端口被其他模型占用且模型不匹配。请更换端口或先杀死旧进程。",
}

def friendly_error(original_exception, context=" "):
    """将技术异常转换为用户友好的错误消息"""
    e = original_exception
    if isinstance(e, requests.exceptions.ConnectionError):
        return FRIENDLY_ERRORS["ConnectionError"]
    elif isinstance(e, requests.exceptions.Timeout):
        return FRIENDLY_ERRORS["Timeout"]
    elif isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 404:
        return f"API 端点不存在，请检查地址格式是否正确。当前地址: {context}"
    elif "model" in str(e).lower() and "not found" in str(e).lower():
        return FRIENDLY_ERRORS["model_not_found"]
    else:
        return f"请求失败: {e}"

# ------------------- 图像编码 -------------------
def encode_image(image_tensor, format="PNG"):
    """将 ComfyUI 图像 tensor 编码为 base64"""
    i = 255. * image_tensor[0].cpu().numpy()
    img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
    if format.upper() == "JPEG" and img.mode == "RGBA":
        img = img.convert("RGB")
    buffered = BytesIO()
    img.save(buffered, format=format.upper())
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# ------------------- 响应提取 -------------------
def extract_response(message):
    """从消息中提取内容，支持 reasoning_content 降级"""
    content = message.get("content", "").strip()
    reasoning = message.get("reasoning_content", "").strip()
    if content:
        return content, None
    elif reasoning:
        return reasoning, "模型仅返回了思考过程，未输出最终答案。已将思考过程作为答案返回。"
    else:
        return "", "模型未返回任何内容。"

# ------------------- URL 规范化 -------------------
def normalize_api_url(url):
    """确保 API URL 以 /v1 结尾"""
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    return url

def get_actual_model_name(port):
    """查询端口上实际运行的模型名称"""
    try:
        resp = requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            if models:
                return models[0]["id"]
    except:
        pass
    return None

# ------------------- 流式请求辅助 -------------------
def stream_chat_completion(api_url, payload, timeout):
    """生成器：流式获取 chat completion 响应"""
    session = get_session(api_url)
    with session.post(
        f"{api_url}/chat/completions",
        json=payload,
        timeout=timeout,
        stream=True
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=False):
            if not line:
                continue
            try:
                # 安全解码，跳过无效字节
                decoded_line = line.decode("utf-8", errors="ignore")
            except:
                continue
            if decoded_line.startswith("data: "):
                data = decoded_line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue