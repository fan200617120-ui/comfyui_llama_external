import json
import re
import requests
from .common import (
    get_session,
    friendly_error,
    normalize_api_url,
    apply_thinking_mode,
    execute_non_stream_chat
)

class LLMAgentPlanner:
    """ Agent 任务规划器：将自然语言需求拆解为结构化工作流步骤。 """

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
                "thinking_mode": (["跟随模型默认", "强制关闭思考", "强制开启思考"], {
                    "default": "跟随模型默认",
                    "tooltip": "控制模型的思考模式。对于不支持思考控制的模型，请选择「跟随模型默认」。"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("plan_json", "plan_text")
    FUNCTION = "plan"
    CATEGORY = "LLM_External"

    def plan(self, api_url, model_name, user_request, system_instruction, temperature, timeout, max_tokens, thinking_mode):
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

        apply_thinking_mode(payload, model_name, thinking_mode)

        try:
            content, is_success = execute_non_stream_chat(api_url, payload, timeout)
            if not is_success:
                return ("[]", content)

            # 稳健的 JSON 数组提取
            parsed_list, raw_text = self._extract_json_array(content)
            if parsed_list is not None:
                return (json.dumps(parsed_list, ensure_ascii=False), raw_text)

            # 降级：尝试解析单个对象
            try:
                parsed = json.loads(content)
                if isinstance(parsed, (dict, list)):
                    result = parsed if isinstance(parsed, list) else [parsed]
                    return (json.dumps(result, ensure_ascii=False), content)
            except (json.JSONDecodeError, ValueError):
                pass

            return ("[]", content)

        except Exception as e:
            print(f"[LLMAgentPlanner] 未知异常: {e}")
            err_msg = friendly_error(e, context=api_url)
            return (err_msg, "")

    @staticmethod
    def _extract_json_array(content: str):
        """提取最外层的 JSON 数组，支持 Markdown 代码块包裹"""
        # 1. 清理 Markdown 代码块
        cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip(), flags=re.MULTILINE)

        # 2. 尝试直接解析
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed, content
        except json.JSONDecodeError:
            pass

        # 3. 降级：使用正则提取最外层数组（支持嵌套）
        stack = 0
        start = -1
        for i, char in enumerate(cleaned):
            if char == '[':
                if stack == 0:
                    start = i
                stack += 1
            elif char == ']':
                stack -= 1
                if stack == 0 and start != -1:
                    candidate = cleaned[start:i+1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, list):
                            return parsed, content
                    except (json.JSONDecodeError, ValueError):
                        pass
                    except Exception as e:
                        print(f"[LLMAgentPlanner] JSON解析异常: {e}")
                    start = -1
        return None, content