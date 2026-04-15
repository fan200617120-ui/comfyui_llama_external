from .llama_nodes import (
    LLMExternalServerAuto,
    LLMExternalServer,
    LLMExternalKiller,
    LLMExternalImageToPrompt,
    LLMExternalTextChat
)
from .ollama_nodes import (
    OllamaServer,
    OllamaImageToPrompt,
    OllamaTextChat
)
from .agent_node import (
    LLMAgentPlanner
)
from .stream_ui_node import LLMStreamUI

NODE_CLASS_MAPPINGS = {
    "LLMExternalServerAuto": LLMExternalServerAuto,
    "LLMExternalServer": LLMExternalServer,
    "LLMExternalKiller": LLMExternalKiller,
    "LLMExternalImageToPrompt": LLMExternalImageToPrompt,
    "LLMExternalTextChat": LLMExternalTextChat,
    "OllamaServer": OllamaServer,
    "OllamaImageToPrompt": OllamaImageToPrompt,
    "OllamaTextChat": OllamaTextChat,
    "LLMAgentPlanner": LLMAgentPlanner,
    "LLMStreamUI": LLMStreamUI,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LLMExternalServerAuto": "自动加载外部LLM（模型文件夹）",
    "LLMExternalServer": "手动加载外部LLM",
    "LLMExternalKiller": "卸载/杀死外部LLM",
    "LLMExternalImageToPrompt": "本地图像反推提示词",
    "LLMExternalTextChat": "本地LLM写提示词",
    "OllamaServer": "Ollama 连接检查",
    "OllamaImageToPrompt": "本地图像反推提示词",
    "OllamaTextChat": "本地LLM写提示词",
    "LLMAgentPlanner": "LLM任务规划器",
    "LLMStreamUI": "LLM 流式输出(UI版)",
}

WEB_DIRECTORY = "./web"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
