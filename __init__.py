# 核心节点（必须存在）
try:
    from .llama_nodes import (
        LLMExternalServerAuto,
        LLMExternalServer,
        LLMExternalKiller,
        LLMExternalImageToPrompt,
        LLMExternalTextChat
    )
    from .agent_node import LLMAgentPlanner
except ImportError as e:
    print(f"[LLM External] 核心节点导入失败: {e}")
    raise

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
    OLLAMA_NODES = {
        "OllamaServer": OllamaServer,
        "OllamaImageToPrompt": OllamaImageToPrompt,
        "OllamaTextChat": OllamaTextChat,
    }
    OLLAMA_DISPLAY_NAMES = {
        "OllamaServer": "Ollama 连接检查",
        "OllamaImageToPrompt": "Ollama 图像反推提示词",
        "OllamaTextChat": "Ollama 写提示词",
    }
    NODE_CLASS_MAPPINGS.update(OLLAMA_NODES)
    NODE_DISPLAY_NAME_MAPPINGS.update(OLLAMA_DISPLAY_NAMES)
    print("[LLM External] Ollama 节点已加载")
except ImportError as e:
    print(f"[LLM External] Ollama 节点导入失败（可选）: {e}")
except Exception as e:
    print(f"[LLM External] Ollama 节点注册失败: {e}")

# 3. 可选：流式 UI 节点（安全导入）
try:
    from .stream_ui_node import LLMStreamUI
    NODE_CLASS_MAPPINGS["LLMStreamUI"] = LLMStreamUI
    NODE_DISPLAY_NAME_MAPPINGS["LLMStreamUI"] = "LLM 流式输出(UI版)"
    print("[LLM External] 流式UI节点已加载")
except ImportError as e:
    print(f"[LLM External] 流式UI节点导入失败（可选）: {e}")
except Exception as e:
    print(f"[LLM External] 流式UI节点注册失败: {e}")

# 4. 可选：多模态流式 UI 节点（安全导入）
try:
    from .stream_image_node import LLMStreamImageToPrompt
    NODE_CLASS_MAPPINGS["LLMStreamImageToPrompt"] = LLMStreamImageToPrompt
    NODE_DISPLAY_NAME_MAPPINGS["LLMStreamImageToPrompt"] = "LLM 图像反推(流式UI版)"
    print("[LLM External] 多模态流式节点已加载")
except ImportError as e:
    print(f"[LLM External] 多模态流式节点导入失败（可选）: {e}")
except Exception as e:
    print(f"[LLM External] 多模态流式节点注册失败: {e}")

WEB_DIRECTORY = "./js"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]