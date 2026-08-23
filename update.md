好的，我来根据您最新的代码修改和新增的参数，生成一份**完整的中英文对照使用说明**，同时更新您的 `README.md`。

---

# 🌟 ComfyUI LLM External 插件完整使用手册

> 将强大的本地大语言模型（LLM）无缝接入 ComfyUI 工作流。支持 Ollama 和 llama.cpp 后端，提供文本对话、图像反推提示词、Agent 任务规划，以及节点内实时流式打字效果。

---

## 📑 目录

1. [功能亮点](#-功能亮点)
2. [安装与前置条件](#-安装与前置条件)
3. [节点参数详解（中英文对照）](#-节点参数详解中英文对照)
   - 3.1 模型加载参数
   - 3.2 基础推理参数
   - 3.3 高级采样参数（DRY / XTC / Mirostat / 动态温度）
   - 3.4 思考模式与推理强度
   - 3.5 服务管理参数
   - 3.6 图像处理参数
4. [节点功能说明](#-节点功能说明)
5. [快速工作流搭建指南](#-快速工作流搭建指南)
6. [参数调优速查表](#-参数调优速查表)
7. [常见问题排查 (FAQ)](#-常见问题排查-faq)

---

## ✨ 功能亮点

- **双后端支持**：原生兼容 Ollama 和 llama.cpp（llama-server.exe）。
- **自动服务管理**：自动启动、复用、卸载 llama-server 进程，配置签名比较避免重复加载。
- **多模态视觉**：支持 LLaVA、Qwen2-VL、Qwen3-VL 等视觉模型进行图生文，最多支持 8 张图片同时输入。
- **高级采样控制**：支持 DRY、XTC、Mirostat、动态温度、min_p、grammar/json_schema 约束等 15+ 精细采样参数。
- **Agent 规划**：将自然语言需求自动拆解为结构化 JSON 工作流。
- **🔥 UI 流式输出**：独占的黑科技，文本在节点框内一边生成一边刷新（类似 ChatGPT 打字效果），支持 Markdown 渲染。
- **自动卸载**：生成完成后自动杀死进程释放显存，适合一次性推理任务。

---

## 📦 安装与前置条件

### 安装
将整个 `comfyui_llama_external` 文件夹放入 ComfyUI 的 `custom_nodes` 目录下。

### 前置条件

**方案一：使用 llama.cpp（推荐）**
1. 下载 [llama.cpp Windows 预编译包](https://github.com/ggml-org/llama.cpp/releases)
2. 解压到本地目录，例如：`F:\AItools\LLM\llama\`
3. 准备至少一个 **GGUF 格式** 的大模型文件，放入 `ComfyUI/models/LLM/` 目录
   - 支持子文件夹，如 `ComfyUI/models/LLM/Qwen/Qwen-7B.gguf`
   - 大小写不敏感，`LLM` 或 `llm` 均可识别

**方案二：使用 Ollama**
1. 安装 [Ollama](https://ollama.com/) 并确保服务运行（默认 `http://127.0.0.1:11434`）
2. 拉取模型：`ollama pull llama3.2` 或 `ollama pull llava:13b`

---

## 🧩 节点参数详解（中英文对照）

### 3.1 模型加载参数（自动加载外部LLM / 手动加载外部LLM）

| 中文名 | 英文名 | 默认值 | 范围 | 说明与用法 |
|--------|--------|--------|------|------------|
| **模型文件** | `model_file` | （下拉选择） | models/LLM 中的 `.gguf` | 选择要加载的大语言模型文件。支持子目录，自动过滤 mmproj 文件。 |
| **视觉投影文件** | `mmproj_file` | 无 | models/LLM 中的 `.gguf`（含 mmproj） | 多模态模型（如 Llava、Qwen-VL）需要此文件。纯文本模型选“无”。 |
| **端口** | `port` | 8080 | 1024~65535 | llama-server 监听的端口。同一端口只能运行一个模型实例。 |
| **GPU 层数** | `gpu_layers` | -1 | -1~99 | 分配到 GPU 的模型层数。`-1` = 自动全部分配，`0` = 纯 CPU。 |
| **上下文长度** | `ctx_size` | 4096 | 512~131072 | 模型能处理的最大 token 数（输入+输出）。越大显存占用越多。 |
| **KV 缓存 K 类型** | `cache_type_k` | 默认(F16) | F16 / q8_0 | KV 缓存数据类型。`q8_0` 减少显存占用，可能略微影响质量。 |
| **KV 缓存 V 类型** | `cache_type_v` | 默认(F16) | F16 / q8_0 | 同 `cache_type_k`，建议两者保持一致。 |
| **MoE 专家上 CPU** | `cpu_moe` | False | True/False | 将 MoE 专家权重全部放到 CPU，显存不足时启用，但会降低速度。 |
| **前 N 层专家上 CPU** | `n_cpu_moe` | 0 | 0~256 | 将前 N 层 MoE 专家放到 CPU。若 `cpu_moe` 为 True，则此项被忽略。 |
| **超时时间** | `timeout` | 180 | 30~900 | API 请求超时秒数。模型推理较慢时可适当调大。 |
| **最大生成 token** | `max_tokens` | 4096 | 256~16384 | 单次生成的最大 token 数。 |
| **强制重载** | `force_reload` | False | True/False | 勾选后强制重启服务，更换模型时需勾选。 |
| **exe 路径** | `exe_path` | （空） | 任意路径 | `llama-server.exe` 完整路径。留空则自动在 PATH 中查找。 |

---

### 3.2 基础推理参数（LLMStreamUI / LLMExternalTextChat / LLMExternalImageToPrompt）

| 中文名 | 英文名 | 默认值 | 范围 | 说明与用法 |
|--------|--------|--------|------|------------|
| **API 地址** | `api_url` | http://127.0.0.1:11434/v1 | 任意 URL | llama-server 或 Ollama 的 API 端点。自动补全 `/v1`。 |
| **模型名称** | `model_name` | （手动输入） | 任意字符串 | 与 `api_url` 对应的模型名称。 |
| **系统提示词** | `system_prompt` | （默认） | 多行文本 | 系统级指令，设定模型角色和行为规范。 |
| **用户提示词** | `user_prompt` / `prompt` | （默认） | 多行文本 | 用户的提问或指令。 |
| **温度** | `temperature` | 0.7 | 0.0~2.0 | 控制随机性。**越低越确定**（0.1 适合事实问答），**越高越有创意**（1.2 适合写作）。 |

---

### 3.3 高级采样参数（仅 LLMStreamUI / LLMExternalTextChat）

> 所有高级参数默认均为“关闭”或“保守值”，普通用户无需修改。遇到特定问题（重复、质量不足）时按需调整。

| 中文名 | 英文名 | 默认值 | 范围 | 说明与用法 |
|--------|--------|--------|------|------------|
| **最小概率采样** | `min_p` | 0.0 | 0.0~1.0 | 过滤概率低于 `min_p * max_prob` 的 token。**0=关闭**，推荐 0.05~0.1，减少低质量输出。 |
| **动态温度范围** | `dynatemp_range` | 0.0 | 0.0~5.0 | 温度随 token 概率动态变化。**0=关闭**，推荐 0.5~2.0，让输出更生动。配合 `dynatemp_exponent`。 |
| **动态温度指数** | `dynatemp_exponent` | 1.0 | 0.1~10.0 | 控制动态温度的曲线形状。**1.0=线性**，>1 更偏向极端调整。 |
| **XTC 概率** | `xtc_probability` | 0.0 | 0.0~1.0 | 随机丢弃部分高概率 token 以增加多样性。**0=关闭**，推荐 0.1~0.5。配合 `xtc_threshold`。 |
| **XTC 阈值** | `xtc_threshold` | 0.1 | 0.0~1.0 | 配合 `xtc_probability`，控制丢弃的 token 范围。一般保持默认。 |
| **重复惩罚** | `repeat_penalty` | 1.0 | 0.1~5.0 | 惩罚已出现过的 token。**1.0=关闭**，推荐 1.05~1.2，减少重复循环。 |
| **DRY 乘数** | `dry_multiplier` | 0.0 | 0.0~5.0 | 基于重复 n-gram 的惩罚力度。**0=关闭**，推荐 0.8~1.5，消除重复模式。 |
| **DRY 基准值** | `dry_base` | 1.75 | 1.0~5.0 | DRY 惩罚的基数，一般保持默认。 |
| **DRY 允许长度** | `dry_allowed_length` | 2 | 1~100 | 允许重复的 token 序列长度。**2**=禁止任意 2-gram 重复。 |
| **Mirostat 模式** | `mirostat` | 0 | 0~2 | **0=关闭**，**1=v1**，**2=v2**。开启后覆盖 temperature/top_p。 |
| **Mirostat 目标熵** | `mirostat_tau` | 5.0 | 0.1~20.0 | Mirostat 的目标熵值，越大输出越随机。建议 5.0。 |
| **Mirostat 学习率** | `mirostat_eta` | 0.1 | 0.001~1.0 | 调整速度，建议 0.1。 |
| **局部典型采样** | `typical_p` | 1.0 | 0.0~1.0 | 选择概率接近典型分布的 token。**1.0=关闭**，推荐 0.9~0.95，使输出更自然。 |
| **BNF 语法约束** | `grammar` | （空） | 多行文本 | BNF 语法限制输出格式。与 `json_schema` 互斥，`json_schema` 优先。 |
| **JSON Schema 约束** | `json_schema` | （空） | 多行文本 | JSON Schema 强制输出符合指定结构的 JSON。优先于 `grammar`。 |

---

### 3.4 思考模式与推理强度

| 中文名 | 英文名 | 默认值 | 范围 | 说明与用法 |
|--------|--------|--------|------|------------|
| **思考模式** | `thinking_mode` | 跟随模型默认 | 跟随/强制关闭/强制开启 | 控制 DeepSeek、GLM、Qwen 系列模型的“思维链”模式。强制开启会输出推理过程。 |
| **推理强度** | `reasoning_effort` | 无 | 无/low/medium/high/xhigh | 仅 **Qwen3.8** 等支持。控制推理深度：xhigh=质量最高，low=速度最快。 |

---

### 3.5 服务管理参数

| 中文名 | 英文名 | 默认值 | 范围 | 说明与用法 |
|--------|--------|--------|------|------------|
| **自动卸载** | `auto_unload` | False | True/False | 生成完成后自动杀死该端口的 llama-server 进程，释放显存。适合一次性任务。 |
| **流式输出** | `stream` | False | True/False | 开启后控制台逐 token 打印。流式 UI 节点强制启用，无需手动设置。 |

---

### 3.6 图像处理参数（LLMExternalImageToPrompt / LLMStreamImageToPrompt）

| 中文名 | 英文名 | 默认值 | 范围 | 说明与用法 |
|--------|--------|--------|------|------------|
| **最大边长** | `max_side` | 1024 | 128~4096 | 输入图片等比缩放到此最大边长。减小可加快编码和推理速度。 |
| **图片输入** | `image` / `image1~image8` | - | IMAGE 张量 | 支持最多 8 张图片同时输入，模型会一次性分析所有图片。 |

---

## 🧩 节点功能说明

| 节点名称 | 英文名 | 功能描述 |
|----------|--------|----------|
| **自动加载外部LLM** | `LLMExternalServerAuto` | 下拉选择 models/LLM 中的模型，自动启动 llama-server。支持子文件夹，大小写不敏感。 |
| **手动加载外部LLM** | `LLMExternalServer` | 手动输入完整路径启动服务，适合高级用户。 |
| **卸载/杀死外部LLM** | `LLMExternalKiller` | 杀死指定端口或所有托管进程，释放显存。 |
| **Ollama 连接检查** | `OllamaServer` | 检查 Ollama 服务状态和模型是否存在。 |
| **llama.cpp 写提示词** | `LLMExternalTextChat` | 纯文本对话，支持高级采样参数。 |
| **Ollama 写提示词** | `OllamaTextChat` | Ollama 后端纯文本对话。 |
| **llama.cpp 图像反推** | `LLMExternalImageToPrompt` | 图生文，支持最多 8 张图片、最大边长缩放、自动卸载。 |
| **Ollama 图像反推** | `OllamaImageToPrompt` | Ollama 后端图生文。 |
| **LLM 任务规划器** | `LLMAgentPlanner` | 将自然语言需求拆解为结构化 JSON 工作流步骤。 |
| **🔥 LLM 流式输出(UI版)** | `LLMStreamUI` | 节点内实时 Markdown 渲染流式输出，支持高级采样参数。 |
| **🔥 LLM 图像反推(流式UI版)** | `LLMStreamImageToPrompt` | 流式 UI 版图生文，支持多图、最大边长、自动卸载。 |

---

## 🚀 快速工作流搭建指南

### 场景 A：本地离线图生提示词（Llama.cpp 完整版）

```
1. 添加 自动加载外部LLM（模型文件夹）
   - 选择模型文件（如 Qwen2-VL-7B.gguf）
   - 选择 mmproj 文件（如有）
   - 设置 gpu_layers = -1，ctx_size = 8192

2. 添加 本地图像反推提示词 (llama.cpp)
   - 连接服务节点的 api_url、model_name、timeout、max_tokens
   - 接入图片（image / image2~image8）
   - 调整 max_side（图片缩放）
   - 启用 auto_unload（可选）

3. 运行即可获得图片描述/提示词
```

### 场景 B：体验流式打字 + 高级采样控制

```
1. 添加 Ollama 连接检查（或 自动加载外部LLM）
2. 添加 LLM 流式输出(UI版)
   - 连接服务节点的 4 个输出口
   - 设置 temperature = 0.9（增加创意）
   - 开启 dry_multiplier = 1.0（消除重复）
   - 开启 min_p = 0.05（过滤低质量）
3. 输入需要长篇大论的问题，运行
4. 观察节点框内实时 Markdown 渲染效果
```

### 场景 C：多图联合理解

```
1. 自动加载外部LLM（选择 Qwen2-VL 模型 + mmproj）
2. 添加 本地图像反推提示词
3. 连接 image、image2、image3 等多个图片输入
4. 提示词："请比较这几张图片的异同，并分别生成描述。"
5. 模型会一次性分析所有图片并输出对比结果
```

---

## 📊 参数调优速查表

| 目标 | 推荐调整 |
|------|----------|
| **减少重复** | `repeat_penalty = 1.1~1.2`，`dry_multiplier = 0.8~1.5` |
| **增加创意** | `temperature = 0.9~1.2`，`dynatemp_range = 0.5~1.5` |
| **提高事实准确性** | `temperature = 0.1~0.3`，关闭 `dry` / `xtc` |
| **输出严格 JSON** | 填写 `json_schema`，`temperature = 0.1` |
| **节省显存** | `cache_type = q8_0`，减小 `ctx_size`，启用 `cpu_moe` |
| **提升速度** | 减小 `max_tokens`，`gpu_layers = -1`，减小 `ctx_size` |
| **更自然的文本** | `typical_p = 0.9~0.95`，`min_p = 0.05~0.1` |
| **代码/诗歌生成** | `temperature = 0.8~1.0`，关闭重复惩罚 |

---

## 🔧 常见问题排查 (FAQ)

### Q1: 报错“找不到 llama-server 可执行文件”
**A**: 在 `自动加载外部LLM` 节点中填写 `exe_path` 为 `llama-server.exe` 的真实完整路径。或确保 `llama-server` 在系统 PATH 中。

### Q2: 自动加载节点下拉列表为空
**A**: 
1. 检查 `ComfyUI/models/LLM/` 目录是否存在
2. 确认模型文件扩展名为 `.gguf`
3. 支持子文件夹（如 `LLM/Qwen/`），也支持 `llm` 小写目录名

### Q3: 流式输出节点框里没有实时打字效果
**A**: 
1. 确认 `web/llm_stream.js` 文件存在
2. 清除浏览器缓存（Ctrl+Shift+Delete）
3. 按 F12 查看控制台是否有 JS 报错

### Q4: 报错“端口已被模型 'xxx' 占用”
**A**: 勾选 `force_reload` 强制重启，或更换端口，或先用 `卸载/杀死外部LLM` 清空端口。

### Q5: 高级采样参数不生效？
**A**: 
1. 确认 `llama-server` 版本 ≥ 0.3.x
2. 参数默认均为关闭（0 或 1.0），需要手动调整才会生效
3. Mirostat 开启后会覆盖 `temperature` 和 `top_p`

### Q6: json_schema 不生效？
**A**: 确保填写的是**合法的 JSON Schema**（不是 JSON 对象本身）。例如：
```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "age": {"type": "integer"}
  }
}
```

### Q7: 流式输出控制台出现乱码（Windows）
**A**: 更新至最新版 `common.py`，已修复 UTF-8 解码问题。

### Q8: 图像反推输出质量差？
**A**: 修改 `prompt` 为更具体的指令，例如：
```
"你是一个专业的 Stable Diffusion 提示词工程师。请仔细观察这张图片，提取主体、环境、光影、画风，输出一段英文提示词。只输出提示词，不要解释。"
```

---

## 📋 更新日志

| 版本 | 更新内容 |
|------|----------|
| 2026-08-23 | 新增高级采样参数：min_p、dynatemp、xtc、repeat_penalty、dry、mirostat、typical_p、grammar、json_schema |
| 2026-08-23 | 新增 `apply_sampling_params` 统一注入函数 |
| 2026-08-23 | 模型扫描支持大小写不敏感（LLM/llm）和递归子文件夹 |
| 2026-08-23 | 修复流式节点重置拼接、SSE 末尾行丢失、content=null 崩溃等问题 |
| 2026-08-23 | 新增 `auto_unload` 自动卸载功能 |
| 2026-08-23 | `exe_path` 支持留空自动查找 PATH |

---

*Made with ❤️ for ComfyUI Community*

> 📌 **注意**：插件不提供模型文件，请自行获取并遵守模型许可证。