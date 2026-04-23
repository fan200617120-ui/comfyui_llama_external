# common.py (20260423)
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
import threading

# === 强制设置 Windows 控制台为 UTF-8 ===
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except:
        pass

# ------------------- 线程安全全局 Session 管理 -------------------
# 每个线程独立一个 session 字典，避免 requests.Session 非线程安全导致崩溃
_local = threading.local()
_all_thread_sessions = []  # 用于清理时遍历所有线程的 session
_lock = threading.Lock()

def get_session(base_url, timeout=30):
    """获取当前线程的带重试机制的 requests Session（线程安全）"""
    # 初始化当前线程的 session 字典
    if not hasattr(_local, 'sessions'):
        _local.sessions = {}
        with _lock:
            _all_thread_sessions.append(_local.sessions)

    sessions = _local.sessions
    if base_url not in sessions:
        session = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=10)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        sessions[base_url] = session
    return sessions[base_url]

def clear_sessions():
    """程序退出时关闭所有线程的所有 session"""
    with _lock:
        for sessions in _all_thread_sessions:
            for url, session in list(sessions.items()):
                try:
                    session.close()
                except:
                    pass
            sessions.clear()
        _all_thread_sessions.clear()

atexit.register(clear_sessions)

# ------------------- 友好错误消息映射 -------------------
FRIENDLY_ERRORS = {
    "ConnectionError": "无法连接到服务。可能原因：\n1. llama-server 或 Ollama 没有启动\n2. 端口被防火墙拦截\n3. 地址填写错误",
    "Timeout": "请求超时。可能原因：\n1. 模型推理太慢（尝试减少上下文长度）\n2. 网络不稳定\n3. 超时设置过短",
    "model_not_found": "模型名称不存在。可能原因：\n1. 模型未下载（Ollama 需先 pull）\n2. 名称拼写错误\n3. 模型文件路径不正确",
    "server_crash": "LLM 服务意外退出。请检查模型兼容性或显存是否不足。",
    "port_conflict": "端口被其他模型占用且模型不匹配。请更换端口或先杀死旧进程。",
}

def friendly_error(original_exception, context=""):
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
    if not url or not isinstance(url, str):
        return ""
    url = url.strip().rstrip("/")
    if not url:
        return ""
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

# ------------------- 统一思考模式注入 -------------------
def apply_thinking_mode(payload: dict, model_name: str, thinking_mode: str):
    """根据模型名称和选择，向 payload 中注入对应的思考模式参数"""
    if thinking_mode == "跟随模型默认":
        return
    model_lower = model_name.lower()
    force_on = (thinking_mode == "强制开启思考")
    if "deepseek" in model_lower:
        payload["chat_template_kwargs"] = {"thinking": force_on}
    elif "glm" in model_lower:
        payload["thinking"] = {"type": "enabled" if force_on else "disabled"}
    elif "qwen" in model_lower or "qwq" in model_lower:
        payload["enable_thinking"] = force_on

# ------------------- 统一非流式请求执行 -------------------
def execute_non_stream_chat(api_url, payload, timeout):
    """
    执行非流式 Chat Completion 请求。
    返回: (result_text: str, is_success: bool)
    """
    try:
        session = get_session(api_url)
        resp = session.post(f"{api_url}/chat/completions", json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("choices") or len(data["choices"]) == 0:
            return "错误：API 返回空的choices列表", False
        msg = data["choices"][0].get("message")
        if not msg:
            return "错误：API 返回的message字段为空", False
        text, warn = extract_response(msg)
        if warn:
            return f"[注意] {warn}\n\n{text}" if text else f"[注意] {warn}", False
        return text, True
    except (requests.exceptions.RequestException, ValueError) as e:
        return friendly_error(e, context=api_url), False

# ------------------- 流式请求辅助 -------------------
def stream_chat_completion(api_url, payload, timeout):
    """生成器：流式获取 chat completion 响应，同时支持 content 和 reasoning_content"""
    session = get_session(api_url)
    with session.post(
        f"{api_url}/chat/completions", json=payload, timeout=timeout, stream=True
    ) as resp:
        resp.raise_for_status()
        buffer = ""
        for chunk in resp.iter_content(chunk_size=8192):
            if not chunk:
                continue
            buffer += chunk.decode("utf-8", errors="ignore")
            
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.startswith("data:"):
                    continue
                
                data = line[5:].strip() if line.startswith("data: ") else line[5:].strip()
                if data == "[DONE]":
                    return
                
                try:
                    if not data:
                        continue
                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content") or delta.get("reasoning_content")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    continue