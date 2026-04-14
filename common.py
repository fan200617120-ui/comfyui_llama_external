import base64
from io import BytesIO
from PIL import Image
import numpy as np

def encode_image(image_tensor):
    """将 ComfyUI 的 IMAGE 张量转换为 base64 字符串（无 data: 前缀）"""
    i = 255. * image_tensor[0].cpu().numpy()
    img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def extract_response(message):
    """
    从 llama.cpp / Ollama 的 OpenAI 兼容响应中提取文本。
    优先取 content，若为空则取 reasoning_content（推理模型）。
    返回 (文本, 警告信息)
    """
    content = message.get("content", "").strip()
    reasoning = message.get("reasoning_content", "").strip()
    if content:
        return content, None
    elif reasoning:
        return "", f"模型只输出了思考过程，未生成最终答案。请提高 max_tokens 参数。\n\n思考过程：\n{reasoning}"
    else:
        return "", "模型未返回任何内容。"

def normalize_api_url(url):
    """规范化 API 地址，确保以 /v1 结尾"""
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    return url

def get_actual_model_name(port):
    """从运行中的 llama-server 获取真实注册的模型名"""
    try:
        import requests
        resp = requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            if models:
                return models[0]["id"]
    except:
        pass
    return None