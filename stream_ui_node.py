import time
import json

from server import PromptServer

from .common import (
    normalize_api_url,
    friendly_error,
    apply_thinking_mode,
    iter_chat_stream,
    apply_sampling_params,
)
from .server_manager import unload_by_api_url


def _push(unique_id, delta=None, reset=False):
    """向后端推送流式更新（支持 reset + delta 同一条消息）"""
    if not unique_id:
        return
    payload = {"node_id": str(unique_id)}
    if reset:
        payload["reset"] = True
    if delta:
        payload["delta"] = delta
    PromptServer.instance.send_sync("llm_stream_update", payload)


class LLMStreamUI:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_url": ("STRING", {"default": "http://127.0.0.1:11434/v1"}),
                "model_name": ("STRING", {"default": "llama3.2"}),
                "system_prompt": ("STRING", {"multiline": True, "default": "You are a helpful AI assistant."}),
                "user_prompt": ("STRING", {"multiline": True, "default": "请开始流式输出..."}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.01}),
                
                # ============ 高级采样参数 ============
                "min_p": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "tooltip": "最小概率采样（0=关闭，推荐 0.05~0.1）"
                }),
                "dynatemp_range": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 5.0,
                    "step": 0.01,
                    "tooltip": "动态温度范围（0=关闭，推荐 0.5~2.0）"
                }),
                "dynatemp_exponent": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.1,
                    "max": 10.0,
                    "step": 0.01,
                    "tooltip": "动态温度指数"
                }),
                "xtc_probability": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "tooltip": "XTC 采样概率（0=关闭，推荐 0.1~0.5）"
                }),
                "xtc_threshold": ("FLOAT", {
                    "default": 0.1,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "tooltip": "XTC 阈值"
                }),
                "repeat_penalty": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.1,
                    "max": 5.0,
                    "step": 0.01,
                    "tooltip": "重复惩罚（1.0=关闭，推荐 1.05~1.2）"
                }),
                "dry_multiplier": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 5.0,
                    "step": 0.01,
                    "tooltip": "DRY 采样乘数（0=关闭，推荐 0.8~1.5）"
                }),
                "dry_base": ("FLOAT", {
                    "default": 1.75,
                    "min": 1.0,
                    "max": 5.0,
                    "step": 0.01,
                    "tooltip": "DRY 基准值"
                }),
                "dry_allowed_length": ("INT", {
                    "default": 2,
                    "min": 1,
                    "max": 100,
                    "step": 1,
                    "tooltip": "DRY 允许长度"
                }),
                "mirostat": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 2,
                    "step": 1,
                    "tooltip": "Mirostat 采样（0=关闭，1=v1，2=v2）\n注意：开启后 temperature/top_p 可能被忽略"
                }),
                "mirostat_tau": ("FLOAT", {
                    "default": 5.0,
                    "min": 0.1,
                    "max": 20.0,
                    "step": 0.1,
                    "tooltip": "Mirostat 目标熵"
                }),
                "mirostat_eta": ("FLOAT", {
                    "default": 0.1,
                    "min": 0.001,
                    "max": 1.0,
                    "step": 0.001,
                    "tooltip": "Mirostat 学习率"
                }),
                "typical_p": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "tooltip": "局部典型采样（1.0=关闭）"
                }),
                "grammar": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "BNF 语法约束（限制输出格式）"
                }),
                "json_schema": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "JSON Schema 约束（优先于 grammar）"
                }),
                # ============ 高级采样参数结束 ============
                
                "timeout": ("INT", {"default": 180}),
                "max_tokens": ("INT", {"default": 4096}),
                "thinking_mode": (["跟随模型默认", "强制关闭思考", "强制开启思考"], {
                    "default": "跟随模型默认",
                    "tooltip": "控制模型的思考模式。"
                }),
                "reasoning_effort": (["无", "low", "medium", "high", "xhigh"], {
                    "default": "无",
                    "tooltip": "推理强度（仅 Qwen3.8 等模型支持）"
                }),
                "auto_unload": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "生成后自动卸载该模型（杀死对应端口进程，释放显存）"
                }),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate_stream"
    CATEGORY = "LLM_External"
    OUTPUT_NODE = True

    def generate_stream(
        self,
        api_url,
        model_name,
        system_prompt,
        user_prompt,
        temperature,
        timeout,
        max_tokens,
        thinking_mode,
        # 高级采样参数
        min_p=0.0,
        dynatemp_range=0.0,
        dynatemp_exponent=1.0,
        xtc_probability=0.0,
        xtc_threshold=0.1,
        repeat_penalty=1.0,
        dry_multiplier=0.0,
        dry_base=1.75,
        dry_allowed_length=2,
        mirostat=0,
        mirostat_tau=5.0,
        mirostat_eta=0.1,
        typical_p=1.0,
        grammar="",
        json_schema="",
        reasoning_effort="无",
        auto_unload=False,
        unique_id=None
    ):
        # 类型保护
        try:
            temperature = float(temperature)
        except (TypeError, ValueError):
            temperature = 0.7
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = 180
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError):
            max_tokens = 4096
        try:
            min_p = float(min_p)
        except (TypeError, ValueError):
            min_p = 0.0
        try:
            dynatemp_range = float(dynatemp_range)
        except (TypeError, ValueError):
            dynatemp_range = 0.0
        try:
            dynatemp_exponent = float(dynatemp_exponent)
        except (TypeError, ValueError):
            dynatemp_exponent = 1.0
        try:
            xtc_probability = float(xtc_probability)
        except (TypeError, ValueError):
            xtc_probability = 0.0
        try:
            xtc_threshold = float(xtc_threshold)
        except (TypeError, ValueError):
            xtc_threshold = 0.1
        try:
            repeat_penalty = float(repeat_penalty)
        except (TypeError, ValueError):
            repeat_penalty = 1.0
        try:
            dry_multiplier = float(dry_multiplier)
        except (TypeError, ValueError):
            dry_multiplier = 0.0
        try:
            dry_base = float(dry_base)
        except (TypeError, ValueError):
            dry_base = 1.75
        try:
            dry_allowed_length = int(dry_allowed_length)
        except (TypeError, ValueError):
            dry_allowed_length = 2
        try:
            mirostat = int(mirostat)
        except (TypeError, ValueError):
            mirostat = 0
        try:
            mirostat_tau = float(mirostat_tau)
        except (TypeError, ValueError):
            mirostat_tau = 5.0
        try:
            mirostat_eta = float(mirostat_eta)
        except (TypeError, ValueError):
            mirostat_eta = 0.1
        try:
            typical_p = float(typical_p)
        except (TypeError, ValueError):
            typical_p = 1.0

        api_url = normalize_api_url(api_url)
        if api_url.startswith("ERROR") or api_url.startswith("错误"):
            _push(unique_id, delta=api_url, reset=True)
            return (api_url,)

        # 重置前端显示
        _push(unique_id, reset=True)

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        # ========== 使用统一的采样参数注入 ==========
        apply_sampling_params(
            payload,
            min_p=min_p,
            dynatemp_range=dynatemp_range,
            dynatemp_exponent=dynatemp_exponent,
            xtc_probability=xtc_probability,
            xtc_threshold=xtc_threshold,
            repeat_penalty=repeat_penalty,
            dry_multiplier=dry_multiplier,
            dry_base=dry_base,
            dry_allowed_length=dry_allowed_length,
            mirostat=mirostat,
            mirostat_tau=mirostat_tau,
            mirostat_eta=mirostat_eta,
            typical_p=typical_p,
            grammar=grammar,
            json_schema=json_schema,
        )

        effort = reasoning_effort if reasoning_effort != "无" else None
        apply_thinking_mode(payload, model_name, thinking_mode, reasoning_effort=effort)

        full_text_parts = []
        pending_delta_parts = []
        last_push_time = time.time()

        try:
            for token in iter_chat_stream(api_url, payload, timeout):
                full_text_parts.append(token)
                pending_delta_parts.append(token)

                now = time.time()
                if len(pending_delta_parts) >= 6 or (now - last_push_time) > 0.05:
                    _push(unique_id, delta="".join(pending_delta_parts))
                    pending_delta_parts.clear()
                    last_push_time = now

            if pending_delta_parts:
                _push(unique_id, delta="".join(pending_delta_parts))

            final_text = "".join(full_text_parts)
            if not final_text or not final_text.strip():
                warn = ("[警告] 模型未返回任何内容。可能原因："
                        "max_tokens 过小、服务端返回空回复、或流中途出错。")
                print(f"[LLM Stream UI] {warn}")
                _push(unique_id, delta=f"\n\n{warn}")
                final_text = warn

            if auto_unload:
                msg, err = unload_by_api_url(api_url)
                if err:
                    print(f"[LLM Stream UI] 卸载失败: {err}")
                else:
                    print(f"[LLM Stream UI] {msg}")

            return (final_text,)

        except Exception as e:
            err = friendly_error(e, context=api_url)
            _push(unique_id, delta=f"\n\n[错误] {err}")
            return (err,)