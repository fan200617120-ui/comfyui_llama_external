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

NODE_CLASS_MAPPINGS = {
    # llama.cpp 节点
    "LLMExternalServerAuto": LLMExternalServerAuto,
    "LLMExternalServer": LLMExternalServer,
    "LLMExternalKiller": LLMExternalKiller,
    "LLMExternalImageToPrompt": LLMExternalImageToPrompt,
    "LLMExternalTextChat": LLMExternalTextChat,
    # Ollama 节点
    "OllamaServer": OllamaServer,
    "OllamaImageToPrompt": OllamaImageToPrompt,
    "OllamaTextChat": OllamaTextChat,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LLMExternalServerAuto": "自动加载外部LLM（模型文件夹）",
    "LLMExternalServer": "手动加载外部LLM",
    "LLMExternalKiller": "卸载/杀死外部LLM",
    "LLMExternalImageToPrompt": "本地图像反推提示词 (llama.cpp)",
    "LLMExternalTextChat": "本地LLM写提示词 (llama.cpp)",
    "OllamaServer": "Ollama 连接检查",
    "OllamaImageToPrompt": "本地图像反推提示词 (Ollama)",
    "OllamaTextChat": "本地LLM写提示词 (Ollama)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]