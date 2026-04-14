ComfyUI LLM External 插件使用手册（Word版）

一、简介

本插件将 llama.cpp 和 Ollama 的本地大模型能力集成到 ComfyUI 中，支持：

- 🔄 自动/手动启动 llama-server，无需离开 ComfyUI 界面

- 🖼️ 图像反推提示词（Image-to-Prompt），支持多模态视觉模型

- 💬 纯文本对话生成提示词，用于 AI 绘画前的创意构思

-  支持思考过程提取（如 DeepSeek-R1 等推理模型）

- ⚡ 请求级 GPU 层数控制，灵活调配显存资源

二、安装教程

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

四、节点详细说明

4.1 服务启动节点

① 自动加载外部LLM（模型文件夹）

节点名：LLMExternalServerAuto

自动扫描指定文件夹内的 .gguf 模型文件，并启动 llama-server。

参数

说明

model_folder

包含 .gguf 文件的文件夹路径

port

服务端口，默认 8080

gpu_layers

GPU 加速层数，-1 为自动全显存

ctx_size

上下文长度，默认 4096

timeout

后续请求的超时时间（秒）

max_tokens

生成的最大 token 数

force_reload

若已存在同端口服务，是否强制重启

exe_path

可选，指定 llama-server.exe 的完整路径

输出：

- api_url：服务的 API 地址（如 http://127.0.0.1:8080/v1）

- model_name：实际加载的模型名称（从服务端获取）

- timeout / max_tokens：传递给后续节点的参数

② 手动加载外部LLM

节点名：LLMExternalServer

手动指定模型文件的完整路径，其他参数同上。

参数

说明

model_path

.gguf 模型文件完整路径

mmproj_path

多模态投影文件路径（仅 Llava 等旧架构需要，Qwen2-VL 等留空）

③ Ollama 连接检查

节点名：OllamaServer

验证 Ollama 服务是否可用，并传递连接信息。

参数

说明

api_url

Ollama 地址，可省略 /v1，插件会自动补全

model_name

要使用的模型名称（如 llava:13b）

timeout / max_tokens

请求超时和生成长度限制

4.2 推理节点

④ 本地图像反推提示词 (llama.cpp)

节点名：LLMExternalImageToPrompt

将图像发送给多模态模型，生成描述性的提示词。

输入

说明

api_url

来自服务启动节点的输出

model_name

来自服务启动节点的输出

image

ComfyUI 的 IMAGE 类型输入

prompt

自定义指令，默认为生成中文提示词

temperature

温度参数，控制随机性

timeout / max_tokens

可使用服务节点的值或手动覆盖

gpu_layers（可选）

请求级 GPU 层数，-1 表示使用服务端默认值

输出：

- STRING：模型生成的提示词文本

⑤ 本地LLM写提示词 (llama.cpp)

节点名：LLMExternalTextChat

纯文本对话，用于根据简短描述扩展详细提示词。

输入

说明

system_prompt

系统角色设定，如“你是一个专业的AI绘画提示词工程师”

user_prompt

用户输入，如“赛博朋克风格的小猫”

其他参数同上



⑥ 本地图像反推提示词 (Ollama) / 本地LLM写提示词 (Ollama)

节点名：OllamaImageToPrompt / OllamaTextChat

功能与 llama.cpp 版本完全一致，后端使用 Ollama 服务。

4.3 管理节点

⑦ 卸载/杀死外部LLM

节点名：LLMExternalKiller

用于手动终止后台的 llama-server 进程。

参数

说明

api_url

要终止的服务地址

kill_all

是否终止所有由本插件启动的服务

五、工作流示例详解

5.1 示例一：基础图像反推

1. 添加 Load Image 节点，选择一张图片。

2. 添加 自动加载外部LLM（模型文件夹）节点，配置模型文件夹路径（如 F:\models\qwen2-vl-7b）。

3. 添加 本地图像反推提示词 (llama.cpp) 节点，将 api_url 和 model_name 从前一步连接过来，image 连接 Load Image 的输出。

4. 添加 CLIP Text Encode (Prompt) 节点，将反推节点输出的字符串作为正向提示词。

5. 连接后续的采样、解码节点，即可生成与输入图片风格相似的图像。

5.2 示例二：纯文本创意扩展

1. 添加 手动加载外部LLM 节点，指定一个擅长创意写作的文本模型（如 qwen2.5-7b-instruct）。

2. 添加 本地LLM写提示词 (llama.cpp) 节点，填写系统提示词和用户输入。

3. 将输出的提示词文本送入 KSampler 流程。

5.3 示例三：Ollama 快速体验

1. 确保 Ollama 已运行且已拉取 llava:13b。

2. 添加 Ollama 连接检查 节点，model_name 填 llava:13b。

3. 添加 本地图像反推提示词 (Ollama) 节点，连接上一步的输出和图像。

4. 后续流程同上。

六、常见问题

6.1 启动节点报错 “找不到执行文件”

- 请检查 exe_path 是否填写正确，确保指向 llama-server.exe。

- 如果使用自动加载节点，请确保模型文件夹中存在 .gguf 文件。

6.2 提示 “端口已被占用” 或 “模型不一致”

- 同一个端口只能运行一个模型。若需更换模型，请先使用 卸载/杀死外部LLM 节点终止旧服务，或勾选 force_reload。

6.3 图像反推无输出或只有思考过程

- 部分推理模型（如 DeepSeek-R1）会先输出 reasoning_content，若最终答案未生成，请提高 max_tokens 值。

- 确保使用的模型支持视觉输入（多模态模型）。

6.4 Ollama 节点报错 “模型未找到”

- 请在 Ollama 中确认已通过 ollama pull <模型名> 下载对应模型。

- 模型名需与 Ollama 中的完全一致（如 llava:13b 而非 llava）。

6.5 显存不足

- 降低 gpu_layers 值，例如设为 20 仅加载部分层到显存。

- 减小 ctx_size（上下文长度）。

- 使用请求级 GPU 层数控制，在推理节点中将 gpu_layers 设为较小值。

七、目录结构

comfyui_llama_external/
├── __init__.py              # 节点注册
├── common.py                # 通用工具函数
├── llama_nodes.py           # llama.cpp 相关节点
├── ollama_nodes.py          # Ollama 相关节点
├── server_manager.py        # 后台进程管理
├── workflow_examples/       # 工作流示例 JSON 文件
└── README.md                # 本说明文档

八、更新日志

v1.1 (2026-04-14)

- 新增请求级 GPU 层数控制

- 修复模型名获取逻辑，从服务端读取真实名称

- Ollama URL 自动规范化处理

- 平台兼容性优化

注意：文档中涉及的 http://127.0.0.1:11434（Ollama 默认地址）、http://127.0.0.1:8080/v1（llama-server 默认 API 地址），若出现“URL拼写可能存在错误，请检查”报错，需确认对应服务已正常启动，且端口未被占用。
