# 核心节点（必须存在）
from .llama_nodes import (
    LLMExternalServerAuto,
    LLMExternalServer,
    LLMExternalKiller,
    LLMExternalImageToPrompt,
    LLMExternalTextChat
)
from .agent_node import LLMAgentPlanner

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# 1. 注册核心节点
CORE_NODES = {
    "LLMExternalServerAuto": LLMExternalServerAuto,
    "LLMExternalServer": LLMExternalServer,
    "LLMExternalKiller": LLMExternalKiller,
    "LLMExternalImageToPrompt": LLMExternalImageToPrompt,
    "LLMExternalTextChat": LLMExternalTextChat,
    "LLMAgentPlanner": LLMAgentPlanner,
}
CORE_DISPLAY_NAMES = {
    "LLMExternalServerAuto": "自动加载外部LLM（模型文件夹）",
    "LLMExternalServer": "手动加载外部LLM",
    "LLMExternalKiller": "卸载/杀死外部LLM",
    "LLMExternalImageToPrompt": "llama.cpp 图像反推提示词",
    "LLMExternalTextChat": "llama.cpp 写提示词",
    "LLMAgentPlanner": "LLM任务规划器",
}
NODE_CLASS_MAPPINGS.update(CORE_NODES)
NODE_DISPLAY_NAME_MAPPINGS.update(CORE_DISPLAY_NAMES)

# 2. 可选：Ollama 节点（安全导入）
try:
    from .ollama_nodes import OllamaServer, OllamaImageToPrompt, OllamaTextChat
    NODE_CLASS_MAPPINGS.update({
        "OllamaServer": OllamaServer,
        "OllamaImageToPrompt": OllamaImageToPrompt,
        "OllamaTextChat": OllamaTextChat,
    })
    NODE_DISPLAY_NAME_MAPPINGS.update({
        "OllamaServer": "Ollama 连接检查",
        "OllamaImageToPrompt": "Ollama 图像反推提示词",
        "OllamaTextChat": "Ollama 写提示词",
    })
except ImportError:
    pass

# 3. 可选：流式 UI 节点（安全导入）
try:
    from .stream_ui_node import LLMStreamUI
    NODE_CLASS_MAPPINGS["LLMStreamUI"] = LLMStreamUI
    NODE_DISPLAY_NAME_MAPPINGS["LLMStreamUI"] = "LLM 流式输出(UI版)"
except ImportError:
    pass

WEB_DIRECTORY = "./js"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]