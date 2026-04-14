import subprocess
import time
import requests
import atexit
import os
import sys

# 全局字典，记录启动的进程
ACTIVE_SERVERS = {}

def cleanup_servers():
    for url, proc in ACTIVE_SERVERS.items():
        if proc:
            proc.kill()
    ACTIVE_SERVERS.clear()
atexit.register(cleanup_servers)

def kill_server(api_url=None, kill_all=False):
    """卸载指定的服务或全部服务"""
    global ACTIVE_SERVERS
    if kill_all:
        for url, proc in ACTIVE_SERVERS.items():
            if proc:
                proc.kill()
                print(f"[LLM External] 已杀死进程: {url}")
        ACTIVE_SERVERS.clear()
        return "已杀死所有外部 LLM 进程"
    elif api_url and api_url in ACTIVE_SERVERS and ACTIVE_SERVERS[api_url]:
        ACTIVE_SERVERS[api_url].kill()
        del ACTIVE_SERVERS[api_url]
        return f"已杀死进程: {api_url}"
    return "未找到对应的进程"

def get_running_model_at_port(port):
    """检查端口是否有服务在运行，并返回其模型名"""
    try:
        resp = requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("data", [])
            if models:
                return models[0]["id"]
    except:
        pass
    return None

def start_llama_server(exe_path, model_path, mmproj_path, port, gpu_layers, ctx_size, force_reload=False):
    """启动 llama-server 并返回 api_url 和 model_name，若端口已存在则直接复用"""
    api_url = f"http://127.0.0.1:{port}/v1"
    expected_model_name = os.path.splitext(os.path.basename(model_path))[0]

    # 如果需要强制重启，先杀死原进程
    if force_reload and api_url in ACTIVE_SERVERS and ACTIVE_SERVERS[api_url]:
        ACTIVE_SERVERS[api_url].kill()
        del ACTIVE_SERVERS[api_url]
        time.sleep(2)

    # 检查端口是否已有服务运行
    if not force_reload:
        running_model = get_running_model_at_port(port)
        if running_model is not None:
            # 检查运行的模型是否与期望一致（如果一致则直接复用）
            if running_model == expected_model_name or True:  # 可以去掉 or True 以启用严格检查
                print(f"[LLM External] 端口 {port} 已有模型 {running_model} 在运行，直接复用。")
                ACTIVE_SERVERS[api_url] = None
                return api_url, running_model, None
            else:
                # 模型不一致，提示用户
                return None, None, f"ERROR: 端口 {port} 上运行的是模型 '{running_model}'，与期望的 '{expected_model_name}' 不一致。请更换端口或先杀死旧进程。"

    # 检查可执行文件
    if not os.path.exists(exe_path):
        return None, None, f"ERROR: 找不到执行文件 {exe_path}"

    # 构建命令行
    cmd = [
        exe_path,
        "-m", model_path,
        "-c", str(ctx_size),
        "-ngl", str(gpu_layers),
        "--port", str(port),
        "--host", "127.0.0.1"
    ]
    if mmproj_path and os.path.exists(mmproj_path):
        cmd.extend(["--mmproj", mmproj_path])

    print(f"[LLM External] 正在静默启动: {' '.join(cmd)}")
    try:
        # 平台判断：Windows 下隐藏窗口
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen(cmd, startupinfo=startupinfo, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            process = subprocess.Popen(cmd)
    except Exception as e:
        return None, None, f"ERROR: 启动失败 {e}"

    print(f"[LLM External] 等待模型加载到显存 (端口 {port})...")
    for i in range(180):
        try:
            if requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=2).status_code == 200:
                # 获取真实模型名
                actual_model = get_running_model_at_port(port)
                if actual_model is None:
                    actual_model = expected_model_name
                print(f"[LLM External] 模型加载完成！实际模型名: {actual_model}")
                ACTIVE_SERVERS[api_url] = process
                return api_url, actual_model, None
        except:
            pass
        if process.poll() is not None:
            return None, None, f"ERROR: llama-server 启动后崩溃，退出代码: {process.returncode}"
        time.sleep(1)
    process.kill()
    return None, None, "ERROR: 模型加载超时 (3分钟)"