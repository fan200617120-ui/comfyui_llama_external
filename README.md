🌟 LLM_External ComfyUI 插件使用手册
将强大的本地大语言模型（LLM）无缝接入 ComfyUI 工作流。支持 Ollama 和 llama.cpp 后端，提供文本对话、图像反推提示词、Agent 任务规划，以及节点内实时流式打字效果。

一、简介
![Workflow Example](https://raw.githubusercontent.com/fan200617120-ui/comfyui_llama_external/main/workflow_examples/llama_image_to_prompt_basic.png)

📑 目录
1. 功能亮点

2. 环境与安装

3. 节点详解
        

  1. 服务管理与启动

  2. 文本对话与生成

  3. 图像理解与反推

  4. 智能体任务规划

4. 经典工作流搭建指南

5. 常见问题排查 (FAQ)

✨ 功能亮点

- 双后端支持：原生兼容 Ollama 和 llama.cpp (llama-server.exe)。

- 自动寻址与复用：自动检测端口模型，避免重复加载浪费显存。

- 多模态视觉：支持 LLaVA、Qwen2-VL 等视觉模型进行图生文。

- Agent 规划：将自然语言需求自动拆解为结构化 JSON 工作流。

- 🔥 UI 流式输出：独占的黑科技，文本在节点框内一边生成一边刷新（类似 ChatGPT 打字效果），告别枯燥等待。

二、安装教程
将整个 LLM_External 文件夹放入 ComfyUI 的 custom_nodes 目录下：

ComfyUI/custom_nodes/
里面包含：
__init__.py
common.py
server_manager.py
llama_nodes.py
ollama_nodes.py
agent_node.py
stream_ui_node.py
web/llm_stream.js

2.1 前置条件

方案一：使用 llama.cpp（推荐）
https://github.com/ggml-org/llama.cpp/releases

1. 下载 llama.cpp Windows 预编译包（例如 llama-b8784-bin-win-cuda-12.4-x64.zip）

2. 解压到本地目录，例如：F:\AItools\LLM\llama\

3. 准备至少一个 GGUF 格式的大模型文件（可以从 HuggingFace 等渠道下载）

📌 注意：插件不提供模型文件，请自行获取并遵守模型许可证。

方案二：使用 Ollama

1. 安装 Ollama（官网地址：https://ollama.com/）并确保服务正在运行（默认 http://127.0.0.1:11434）

2. 拉取支持视觉的模型，例如：

ollama pull llava:13b
ollama pull bakllava

2.2 安装插件

1. 进入 ComfyUI 的 custom_nodes 目录：

ComfyUI_windows_portable\ComfyUI\custom_nodes\

1. 克隆本仓库或解压插件压缩包到该目录，确保文件夹名为 comfyui_llama_external。

2. 重启 ComfyUI。

2.3 安装 Python 依赖

插件依赖 requests、Pillow、numpy，通常 ComfyUI 已内置。若缺失，可在 ComfyUI 的 Python 环境中执行：

.\python_embeded\python.exe -m pip install requests

对于便携版 ComfyUI，请使用其自带的 python_embeded 目录下的 Python 解释器。


三、快速上手工作流

以下是一个典型的图像反推提示词工作流：

1. 加载图像 → 使用 Load Image 节点

2. 启动 llama.cpp 服务 → 使用 自动加载外部LLM（模型文件夹）节点

3. 反推提示词 → 连接 本地图像反推提示词 (llama.cpp) 节点

4. 生成图像 → 将输出的提示词送入 CLIP Text Encode 等节点

示例工作流：workflow_examples/example_basic.png（插件目录下的 workflow_examples 文件夹提供了可直接拖入 ComfyUI 的 JSON 工作流示例。）

四、🧩 节点详解
一、 服务管理与启动

用于在 ComfyUI 内部一键启动或管理本地 LLM 推理服务。

1. 自动加载外部LLM（模型文件夹） (LLMExternalServerAuto)

功能：传入一个包含 .gguf 模型的文件夹路径，自动识别模型和 mmproj（多模态投影层），并启动服务。

必填参数：

- model_folder：模型所在的文件夹路径。

- port：推理端口（默认 8080）。

- gpu_layers：GPU 加速层数（-1 为自动全显存）。

可选参数：

- exe_path：llama-server.exe 的绝对路径（需根据你的实际安装位置修改）。

- force_reload：强制重启（更换模型时必勾）。

2. 手动加载外部LLM (LLMExternalServer)

功能：通过精准的文件路径启动服务，适合高级玩家。

区别：需要手动指定 model_path 和 mmproj_path 的完整文件名。

3. 卸载/杀死外部LLM (LLMExternalKiller)

功能：释放显存。可杀死指定端口的进程，也可勾选 kill_all 一键清空所有由本插件启动的进程。

4. Ollama 连接检查 (OllamaServer)

功能：检查 Ollama 是否运行，验证指定的模型是否已下载。

注意：api_url 填写原始地址（如 http://127.0.0.1:11434），节点会自动补全 /v1。

联动技巧：以上 4 个节点的输出均为 (api_url, model_name, timeout, max_tokens)。直接将这四个输出口连到下游对话节点对应的输入口，无需重复填写地址和模型名！

二、 文本对话与生成

接收文本提示词，输出 LLM 生成的结果。

1. 本地LLM写提示词 (LLMExternalTextChat / OllamaTextChat)

功能：纯文本对话。适合让 LLM 扮演“提示词工程师”编写 Midjourney/SD 提示词。

参数：system_prompt（设定角色）、user_prompt（具体需求）、temperature（创意度，0.1-2.0）。

输出：(STRING) 生成的文本。

2. 🔥 LLM 流式输出(UI版) (LLMStreamUI) 【明星节点】

功能：在节点内部提供一个 200px 高的文本框，实时显示 LLM 生成的每一个字。

适用场景：长文生成、写代码、写诗，需要实时观察模型输出以防跑偏时使用。

注意：虽然界面上看起来是在“节点内显示”，但它依然有一个 final_text 输出口，可以继续连给下游节点（如保存为 txt）。

三、 图像理解与反推

输入 ComfyUI 的图像张量（IMAGE），输出对图像的描述或可用于重绘的提示词。

本地图像反推提示词 (LLMExternalImageToPrompt / OllamaImageToPrompt)

功能：图生文。喂给它一张图，它还你一段高质量的 Prompt。

必填：image（接入任意图像节点）、prompt（对图像的指令，如“请用中文详细描述并提取提示词”）。

模型要求：必须使用多模态模型（如 Ollama 的 llava，或 llama.cpp 加载了 mmproj 的模型）。

四、 智能体任务规划

LLM任务规划器 (LLMAgentPlanner)

功能：输入一句模糊的需求（如“帮我做个赛博朋克风格的小猫视频”），LLM 会输出结构化的 JSON 数组，拆解为具体步骤。

输出：

- plan_json：纯 JSON 字符串，可供后续代码节点解析执行。

- plan_text：原始文本备份。

🚀 经典工作流搭建指南

场景 A：最简 Ollama 文本生成 (0 配置)

1. 添加 Ollama 连接检查，填入默认地址和模型名（如 llama3）。

2. 添加 本地LLM写提示词，将上一个节点的 4 个输出口直接连线到这个节点的对应输入口。

3. 在 user_prompt 输入你的需求，运行。

场景 B：本地离线图生提示词 (Llama.cpp)

1. 添加 自动加载外部LLM，填入 Qwen2-VL 或 LLaVA 的模型文件夹路径，修改 exe_path。

2. 添加 本地图像反推提示词，连好服务节点，接入一张图片，运行。

3. 将输出的 STRING 连入 CLIP Text Encode，直接用于生图。

场景 C：体验 UI 流式打字效果

1. 添加 Ollama 连接检查。

2. 添加 LLM 流式输出(UI版)。

3. 连线。输入一个需要长篇大论的问题（如“写一篇800字的科幻小说开头”）。

4. 点击运行，盯着节点框看效果。

🔧 常见问题排查 (FAQ)

Q1: 报错 找不到 llama-server 可执行文件

A: 打开 自动加载外部LLM 节点，将 exe_path 修改为你电脑上 llama-server.exe 的真实绝对路径。

Q2: 报错 端口 8080 已被模型 'xxx' 占用，与期望的 'yyy' 不一致

A: 你正在尝试加载一个新模型，但 8080 端口还在跑旧模型。解决方法：勾选 force_reload 强制重启，或者先连一个 卸载/杀死外部LLM 节点清空端口，也可以换一个端口（如 8081）。

Q3: 流式输出节点控制台出现乱码（如 è¿™æ˜¯），且每个字重复两遍

A: 你使用的是旧版本代码。请更新至最新版 common.py，新版已彻底修复 UTF-8 解码错位与双重打印问题。

Q4: 使用了 LLM 流式输出(UI版)，但节点框里没有实时打字效果？

A: 请按顺序检查：

1. 确认 __init__.py 中包含 WEB_DIRECTORY = "./web"。

2. 确认 web/llm_stream.js 文件存在且路径正确。

3. 清除浏览器缓存（Ctrl+Shift+Delete），或使用无痕模式打开 ComfyUI。

4. 按 F12 打开控制台，查看是否有 JS 加载报错。

Q5: Ollama 报错 模型 'xxx' 未找到

A: 请先打开系统终端/命令行，运行 ollama pull xxx 下载模型后重试。

Q6: 图像反推节点输出的全是废话，没有提示词？

A: 这是 Prompt（指令）写得太模糊。建议将节点里的 prompt 修改为更具体的指令，例如：

"你是一个专业的 Stable Diffusion 提示词工程师。请仔细观察这张图片，提取其中的主体、环境、光影、画风，并输出一段英文提示词，格式为：主体描述, 环境背景, 光影效果, 艺术风格, 画质词。只输出提示词，不要解释。"

*Made with ❤️ for ComfyUI Community*

注意：文档中涉及的 Ollama 默认地址 http://127.0.0.1:11434，若出现“URL拼写可能存在错误，请检查”报错，需确认 Ollama 服务已正常启动，且该端口未被其他程序占用。
