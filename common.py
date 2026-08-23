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
import re
import json
import codecs
import folder_paths

# === 强制 Windows 控制台为 UTF-8 ===
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

# 确保 stdout/stderr 可输出任意 Unicode。
try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ------------------- 全局 Session 管理 -------------------
_session_cache = {}

def _session_key(base_url):
    """以 scheme://host:port 作为缓存键"""
    m = re.match(r"^(https?://[^/]+)", (base_url or "").strip())
    if m:
        return m.group(1).lower()
    return (base_url or "").strip().rstrip("/")

def get_session(base_url, timeout=30):
    key = _session_key(base_url)
    if key not in _session_cache:
        session = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=10)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        _session_cache[key] = session
    return _session_cache[key]

def clear_sessions():
    for key, session in list(_session_cache.items()):
        try:
            session.close()
        except Exception:
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

def friendly_error(original_exception, context=""):
    e = original_exception
    if isinstance(e, requests.exceptions.ConnectionError):
        return FRIENDLY_ERRORS["ConnectionError"]
    elif isinstance(e, requests.exceptions.Timeout):
        return FRIENDLY_ERRORS["Timeout"]
    elif isinstance(e, requests.exceptions.HTTPError) and e.response is not None and e.response.status_code == 404:
        return f"API 端点不存在，请检查地址格式是否正确。当前地址: {context}"
    elif "model" in str(e).lower() and "not found" in str(e).lower():
        return FRIENDLY_ERRORS["model_not_found"]
    else:
        return f"请求失败: {e}"

# ------------------- 图像编码（支持最大边长缩放） -------------------
def encode_image(image_tensor, format="PNG", max_side=None):
    if image_tensor is None:
        return ""
    try:
        i = 255. * image_tensor[0].cpu().numpy()
    except (IndexError, AttributeError):
        return ""
    img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

    if max_side and max_side > 0:
        w, h = img.size
        long_edge = max(w, h)
        if long_edge > max_side:
            scale = max_side / float(long_edge)
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            img = img.resize((new_w, new_h), resample=Image.BICUBIC)
            print(f"[LLM External] 图片已缩放至 {new_w}x{new_h} (最大边长 {max_side})")

    if format.upper() == "JPEG" and img.mode == "RGBA":
        img = img.convert("RGB")

    buffered = BytesIO()
    img.save(buffered, format=format.upper())
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# ------------------- 响应提取 -------------------
def extract_response(message):
    if not isinstance(message, dict):
        return "", "模型返回的消息格式异常。"
    content = (message.get("content") or "").strip()
    reasoning = (message.get("reasoning_content") or "").strip()
    if content:
        return content, None
    elif reasoning:
        return reasoning, "模型仅返回了思考过程，未输出最终答案。已将思考过程作为答案返回。"
    else:
        return "", "模型未返回任何内容。"

# ------------------- URL 规范化 -------------------
def normalize_api_url(url):
    if not url or not isinstance(url, str):
        return ""
    url = url.strip().rstrip("/")
    if not url:
        return ""
    if not url.endswith("/v1"):
        url += "/v1"
    return url

def get_actual_model_name(port):
    try:
        resp = requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            if models:
                return models[0]["id"]
    except Exception:
        pass
    return None

# ------------------- LLM 模型文件扫描（支持不区分大小写 & 递归子文件夹） -------------------
def get_llm_folder():
    try:
        llm_dir = os.path.join(folder_paths.models_dir, "LLM")
        if os.path.isdir(llm_dir):
            if "LLM" not in folder_paths.folder_names_and_paths:
                folder_paths.folder_names_and_paths["LLM"] = ([llm_dir], set())
            return llm_dir

        llm_dir_lower = os.path.join(folder_paths.models_dir, "llm")
        if os.path.isdir(llm_dir_lower):
            if "LLM" not in folder_paths.folder_names_and_paths:
                folder_paths.folder_names_and_paths["LLM"] = ([llm_dir_lower], set())
            else:
                paths, exts = folder_paths.folder_names_and_paths["LLM"]
                if llm_dir_lower not in paths:
                    paths.append(llm_dir_lower)
            return llm_dir_lower

        return None
    except Exception:
        return None

def _scan_gguf_files(folder, include_mmproj=False):
    if not folder or not os.path.isdir(folder):
        return []
    results = []
    for root, dirs, files in os.walk(folder):
        for f in files:
            if not f.endswith('.gguf'):
                continue
            lower = f.lower()
            is_mmproj = 'mmproj' in lower
            if include_mmproj == is_mmproj:
                rel = os.path.relpath(os.path.join(root, f), folder)
                rel = rel.replace('\\', '/')
                results.append(rel)
    return sorted(results)

def get_gguf_files():
    folder = get_llm_folder()
    return _scan_gguf_files(folder, include_mmproj=False)

def get_mmproj_files():
    folder = get_llm_folder()
    return _scan_gguf_files(folder, include_mmproj=True)

def parse_kv_cache_type(value):
    if value == "q8_0":
        return "q8_0"
    return "f16"

# ------------------- 统一思考模式注入 -------------------
def apply_thinking_mode(payload: dict, model_name: str, thinking_mode: str, reasoning_effort: str = None):
    model_lower = (model_name or "").lower()

    if thinking_mode in ("强制开启思考", "强制关闭思考"):
        force_on = (thinking_mode == "强制开启思考")
        if "deepseek" in model_lower:
            payload["chat_template_kwargs"] = {"thinking": force_on}
        elif "glm" in model_lower:
            payload["thinking"] = {"type": "enabled" if force_on else "disabled"}
        elif "qwen" in model_lower or "qwq" in model_lower:
            payload["enable_thinking"] = force_on

    if reasoning_effort and reasoning_effort != "无" and ("qwen" in model_lower or "qwq" in model_lower):
        payload["reasoning_effort"] = reasoning_effort

# ------------------- 统一采样参数注入（新增） -------------------
def apply_sampling_params(payload: dict, **kwargs):
    """
    统一注入高级采样参数到 payload。
    支持 min_p, dynatemp_range, dynatemp_exponent, xtc_probability, xtc_threshold,
    repeat_penalty, dry_multiplier, dry_base, dry_allowed_length,
    mirostat, mirostat_tau, mirostat_eta, typical_p, grammar, json_schema。
    """
    # min_p
    val = kwargs.get('min_p')
    if val is not None and val > 0.0:
        payload['min_p'] = val
    
    # dynatemp
    val = kwargs.get('dynatemp_range')
    if val is not None and val > 0.0:
        payload['dynatemp_range'] = val
        payload['dynatemp_exponent'] = kwargs.get('dynatemp_exponent', 1.0)
    
    # xtc
    val = kwargs.get('xtc_probability')
    if val is not None and val > 0.0:
        payload['xtc_probability'] = val
        payload['xtc_threshold'] = kwargs.get('xtc_threshold', 0.1)
    
    # repeat_penalty
    val = kwargs.get('repeat_penalty')
    if val is not None and val != 1.0:
        payload['repeat_penalty'] = val
    
    # dry
    val = kwargs.get('dry_multiplier')
    if val is not None and val > 0.0:
        payload['dry_multiplier'] = val
        payload['dry_base'] = kwargs.get('dry_base', 1.75)
        payload['dry_allowed_length'] = kwargs.get('dry_allowed_length', 2)
    
    # mirostat
    val = kwargs.get('mirostat')
    if val is not None and val > 0:
        payload['mirostat'] = val
        payload['mirostat_tau'] = kwargs.get('mirostat_tau', 5.0)
        payload['mirostat_eta'] = kwargs.get('mirostat_eta', 0.1)
    
    # typical_p
    val = kwargs.get('typical_p')
    if val is not None and val < 1.0:
        payload['typical_p'] = val
    
    # grammar
    val = kwargs.get('grammar')
    if val and isinstance(val, str) and val.strip():
        payload['grammar'] = val.strip()
    
    # json_schema（优先于 grammar）
    val = kwargs.get('json_schema')
    if val and isinstance(val, str) and val.strip():
        try:
            schema = json.loads(val)
            payload['response_format'] = {"type": "json_schema", "json_schema": schema}
        except json.JSONDecodeError:
            # 降级：如果解析失败，尝试作为 grammar 使用
            if 'grammar' not in payload:
                payload['grammar'] = val.strip()

# ------------------- 统一非流式请求执行 -------------------
def execute_non_stream_chat(api_url, payload, timeout):
    try:
        session = get_session(api_url)
        resp = session.post(f"{api_url}/chat/completions", json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, dict):
            return "错误：API 响应格式异常", False

        err = data.get("error")
        if err:
            msg = err.get("message", err) if isinstance(err, dict) else err
            return f"错误：服务端返回错误：{msg}", False

        choices = data.get("choices") or []
        if not choices:
            return "错误：API 返回空的choices列表", False

        msg = choices[0].get("message")
        if not msg:
            return "错误：API 返回的message字段为空", False

        text, warn = extract_response(msg)
        if warn:
            return (f"[注意] {warn}\n\n{text}" if text else f"[注意] {warn}"), False
        return text, True

    except (requests.exceptions.RequestException, ValueError) as e:
        return friendly_error(e, context=api_url), False

# ------------------- 流式请求辅助 -------------------
def iter_chat_stream(api_url, payload, timeout):
    session = get_session(api_url)

    def _parse_data(data):
        try:
            obj = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(obj, dict):
            return None
        err = obj.get("error")
        if err:
            msg = err.get("message", err) if isinstance(err, dict) else str(err)
            raise RuntimeError(f"服务端在流中返回错误：{msg}")
        try:
            choices = obj.get("choices") or []
            delta = (choices[0] or {}).get("delta") or {}
            return delta.get("content") or delta.get("reasoning_content") or None
        except (AttributeError, IndexError, KeyError, TypeError):
            return None

    with session.post(
        f"{api_url}/chat/completions", json=payload, timeout=timeout, stream=True
    ) as resp:
        resp.raise_for_status()

        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        buffer = ""
        done = False

        for chunk in resp.iter_content(chunk_size=8192):
            if not chunk:
                continue
            buffer += decoder.decode(chunk)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.rstrip("\r")
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data:
                    continue
                if data == "[DONE]":
                    done = True
                    break
                token = _parse_data(data)
                if token:
                    yield token
            if done:
                break

        buffer += decoder.decode(b"", final=True)

        if not done and buffer:
            line = buffer.rstrip("\r")
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    token = _parse_data(data)
                    if token:
                        yield token

def stream_chat_completion(api_url, payload, timeout):
    yield from iter_chat_stream(api_url, payload, timeout)