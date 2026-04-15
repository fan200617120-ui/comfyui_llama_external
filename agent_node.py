import json
import re
from .common import get_session, friendly_error

class LLMAgentPlanner:
    """
    Agent 任务规划器：将自然语言需求拆解为结构化工作流步骤。
    输出格式为 JSON 数组，每个步骤包含 step_name, action, params。
    可用于后续节点自动化执行（需配合自定义流程）。
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:11434/v1"}),
                "model_name": ("STRING", {"default": "llama3.2"}),
                "user_request": ("STRING", {"multiline": True, "default": "我想做一个赛博朋克风格的小猫视频"}),
                "system_instruction": ("STRING", {"multiline": True, "default": "你是一个任务规划专家。请将用户需求拆解为可在ComfyUI中执行的具体步骤，用JSON数组格式输出，每个步骤包含：step_name(步骤名称), action(动作类型，如generate_prompt, run_comfyui, tts等), params(参数字典)。只输出JSON，不要其他文字。"}),
                "temperature": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0, "step": 0.1}),
                "timeout": ("INT", {"default": 60, "min": 30, "max": 300}),
                "max_tokens": ("INT", {"default": 1024, "min": 256, "max": 4096}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("plan_json", "plan_text")
    FUNCTION = "plan"
    CATEGORY = "LLM_External"

    def plan(self, api_url, model_name, user_request, system_instruction, temperature, timeout, max_tokens):
        from .common import normalize_api_url
        api_url = normalize_api_url(api_url)
        if api_url.startswith("ERROR") or api_url.startswith("错误"):
            return (api_url, "")

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_request}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

        try:
            session = get_session(api_url)
            resp = session.post(f"{api_url}/chat/completions", json=payload, timeout=timeout)
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
            content = msg.get("content", "").strip()

            # 修正：更稳健的 JSON 提取
            # 使用非贪婪匹配找出所有可能的 JSON 数组
            json_candidates = re.findall(r'\[[\s\S]*?\]', content)
            for candidate in json_candidates:
                try:
                    parsed = json.loads(candidate)
                    # 确保解析后是列表（任务规划应为列表）
                    if isinstance(parsed, list):
                        return (json.dumps(parsed, ensure_ascii=False), content)
                except:
                    continue

            # 如果没有提取到合法 JSON，返回空对象和原始文本供用户检查
            return ("[]", content)
        except Exception as e:
            err_msg = friendly_error(e, context=api_url)
            return (err_msg, "")