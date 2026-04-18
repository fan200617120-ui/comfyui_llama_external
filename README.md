# 📖 LLM_External ComfyUI 插件使用手册

**ComfyUI LLM External** 是一个为 ComfyUI 提供本地大语言模型（LLM）和视觉多模态模型集成的自定义节点包。
它支持通过 Ollama、llama.cpp、LM Studio 等兼容 OpenAI API 的后端，在 ComfyUI 工作流中直接调用 LLM 进行文本生成、图像反推、任务规划等操作。

---

## 核心特性

- 🚀 **流式输出（UI 版）**：实时打字机效果，支持 Markdown 渲染，体验媲美 ChatGPT
- 🖼️ **多模态支持**：支持 LLaVA、Qwen2-VL 等视觉模型，实现图像反推提示词
- 🧠 **思考模式控制**：针对 DeepSeek、Qwen、GLM 等模型，可强制开启/关闭推理思考过程
- 🔧 **服务自动管理**：自动启动/复用 llama-server 进程，支持显存优化
- 🛡️ **健壮错误处理**：友好的中文错误提示，降低调试门槛

![Workflow Example](https://raw.githubusercontent.com/fan200617120-ui/comfyui_llama_external/main/workflow_examples/llama_image_to_prompt_basic.png)

---

## 📑 目录

1. 功能亮点
2. 环境与安装
3. 节点详解
   - 服务管理与启动
   - 文本对话与生成
   - 图像理解与反推
   - 智能体任务规划
4. 经典工作流搭建指南
5. 常见问题排查 (FAQ)

---

## ✨ 功能亮点

- 双后端支持：原生兼容 Ollama 和 llama.cpp (llama-server.exe)
- 自动寻址与复用：自动检测端口模型，避免重复加载浪费显存
- 多模态视觉：支持 LLaVA、Qwen2-VL 等视觉模型进行图生文
- Agent 规划：将自然语言需求自动拆解为结构化 JSON 工作流
- 🔥 **UI 流式输出**：独占黑科技，文本在节点框内一边生成一边刷新（类似 ChatGPT 打字效果），告别枯燥等待

![Workflow Example](https://raw.githubusercontent.com/fan200617120-ui/comfyui_llama_external/main/workflow_examples/llama_image_to_prompt_basic_new.png)

---

## 二、安装教程

将整个 `LLM_External` 文件夹放入 ComfyUI 的 `custom_nodes` 目录下：

```
ComfyUI/custom_nodes/
├── __init__.py
├── common.py
├── server_manager.py
├── llama_nodes.py
├── ollama_nodes.py
├── agent_node.py
├── stream_ui_node.py
└── js/llm_stream.js
```

---

### 2.1 前置条件

#### 方案一：使用 llama.cpp（推荐）

1. 下载 llama.cpp Windows 预编译包
   例如：`llama-b8784-bin-win-cuda-12.4-x64.zip`
2. 解压到本地目录，例如：
   ```
    D:\AItools\LLM\llama\
   ```
3. 准备至少一个 GGUF 格式大模型文件（从 HuggingFace 等渠道下载）

> 📌 注意：插件不提供模型文件，请自行获取并遵守模型许可证。

#### 方案二：使用 Ollama

1. 安装 Ollama：https://ollama.com/
   确保服务运行在默认地址 `http://127.0.0.1:11434`

2. 拉取视觉模型：
   ```bash
   ollama pull llava:13b
   ollama pull bakllava
   ```

---

### 2.2 安装插件

1. 进入 ComfyUI 的 `custom_nodes` 目录：
   ```
   ComfyUI_windows_portable\ComfyUI\custom_nodes\
   ```

2. 克隆本仓库或解压插件压缩包到该目录，确保文件夹名为 `comfyui_llama_external`

3. 重启 ComfyUI

---

### 2.3 安装 Python 依赖

插件依赖 `requests`、`Pillow`、`numpy`，通常 ComfyUI 已内置。
若缺失，在 ComfyUI 环境中执行：

```bash
.\python_embeded\python.exe -m pip install requests
```

> 便携版请使用自带 `python_embeded` 目录下的解释器

---

## 节点概览

| 节点名称 | 功能描述 |
|---------|----------|
| 自动加载外部LLM（模型文件夹） | 指定文件夹，自动扫描 .gguf 模型并启动 llama-server |
| 手动加载外部LLM | 手动指定模型文件路径和 mmproj 文件路径启动服务 |
| 卸载/杀死外部LLM | 停止指定端口或所有托管的 llama-server 进程 |
| llama.cpp 写提示词 | 纯文本对话生成（非流式） |
| llama.cpp 图像反推提示词 | 上传图像，生成描述或绘画提示词（非流式） |
| Ollama 连接检查 | 验证 Ollama 服务状态及模型可用性 |
| Ollama 写提示词 | 通过 Ollama 进行纯文本生成 |
| Ollama 图像反推提示词 | 通过 Ollama 视觉模型生成图像描述 |
| LLM 流式输出(UI版) | 推荐：纯文本流式对话，实时显示 Markdown |
| LLM 图像反推(流式UI版) | 推荐：上传图像，流式返回描述，支持 Markdown |
| LLM任务规划器 | 将自然语言需求拆解为 JSON 工作流步骤 |

---

## 三、快速上手工作流

典型图像反推提示词流程：

1. 加载图像 → 使用 `Load Image` 节点
2. 启动 llama.cpp 服务 → 使用 `自动加载外部LLM（模型文件夹）` 节点
3. 反推提示词 → 连接 `本地图像反推提示词 (llama.cpp)` 节点
4. 生成图像 → 将输出提示词送入 `CLIP Text Encode` 等节点

示例工作流位于插件目录：
`workflow_examples/example_basic.png`

---

## 🧩 节点详解

### 一、服务管理与启动

用于在 ComfyUI 内部一键启动或管理本地 LLM 推理服务。

#### 1. 自动加载外部LLM（模型文件夹）
功能：传入包含 .gguf 模型的文件夹路径，自动识别模型与 mmproj，并启动服务。

**必填参数**
- `model_folder`：模型所在文件夹路径
- `port`：推理端口（默认 8080）
- `gpu_layers`：GPU 加速层数（-1 为自动全显存）

**可选参数**
- `exe_path`：llama-server.exe 绝对路径
- `force_reload`：强制重启（更换模型时必勾）

#### 2. 手动加载外部LLM
通过完整路径启动服务，适合高级用户。

#### 3. 卸载/杀死外部LLM
释放显存，可杀死指定端口或全部插件启动的进程。

#### 4. Ollama 连接检查
检查 Ollama 是否运行，验证模型是否已下载。

> 联动技巧：
> 以上 4 个节点输出均为 `(api_url, model_name, timeout, max_tokens)`，
> 可直接连线到下游对话节点，无需重复填写。

---

## 📝 参数说明（通用）

| 参数 | 类型 | 说明 |
|-----|-----|------|
| api_url | STRING | LLM 服务 API 地址，通常以 `/v1` 结尾 |
| model_name | STRING | 模型名称（需与服务端一致） |
| system_prompt / user_prompt | STRING | 系统指令与用户输入，支持多行 |
| temperature | FLOAT | 生成随机性（0-2），越高越有创造性 |
| max_tokens | INT | 最大生成 token 数 |
| timeout | INT | API 请求超时时间（秒） |
| stream | BOOLEAN | 是否启用流式输出（仅非 UI 节点） |
| thinking_mode | 下拉选项 | 思考模式控制（默认/强制关闭/强制开启） |

---

## 🚀 经典工作流搭建指南

### 场景 A：最简 Ollama 文本生成
1. 添加 `Ollama 连接检查`，使用默认地址和模型
2. 添加 `本地LLM写提示词`，连线 4 个输出
3. 填写 `user_prompt` 运行

### 场景 B：本地离线图生提示词
1. 添加 `自动加载外部LLM`，填写 Qwen2-VL / LLaVA 路径
2. 添加 `本地图像反推提示词`，连接图片
3. 输出 STRING 连入 CLIP 用于生图

### 场景 C：UI 流式打字效果
1. 添加 `Ollama 连接检查`
2. 添加 `LLM 流式输出(UI版)`
3. 输入长文本需求，运行即可看到实时打字效果

---

## 🔧 常见问题排查 (FAQ)

### Q1: 报错 找不到 llama-server 可执行文件
A: 在 `自动加载外部LLM` 节点中，将 `exe_path` 改为你电脑上真实路径。

### Q2: 端口 8080 已被占用
A: 勾选 `force_reload` 强制重启，或使用 `卸载/杀死外部LLM`，或更换端口（如 8081）。

### Q3: 流式输出乱码、重复两遍
A: 更新到最新版 `common.py`，已彻底修复 UTF-8 解码问题。

### Q4: 节点框里没有打字机效果？
A:
1. 确认 `__init__.py` 中有 `WEB_DIRECTORY = "./web"`
2. 确认 `web/llm_stream.js` 存在
3. 浏览器强制刷新缓存：Ctrl+Shift+Delete
4. F12 查看控制台是否有 JS 加载错误

### Q5: Ollama 报错模型未找到
A: 先在命令行执行 `ollama pull 模型名` 下载。

### Q6: 图像反推全是废话
A: 把提示词换成专业指令，例如：
```
你是一个专业 Stable Diffusion 提示词工程师。仔细观察图片，提取主体、环境、光影、画风，输出一段英文提示词。格式：主体,背景,光影,风格,画质。只输出提示词。
```

---

## 🔧 高级技巧

- **多轮对话**：将历史消息拼接到 `user_prompt`
- **性能调优**：llama.cpp 调整 `gpu_layers=-1`，Ollama 修改 Modelfile
- **工作流联动**：LLM 输出直接连 CLIP Text Encode，全自动出图

---

## 📄 许可证
本项目采用 MIT License 开源。

## 🙏 致谢
- ComfyUI
- Ollama
- llama.cpp

---

**用自然语言驱动你的 ComfyUI 创作吧！🎨✨**
