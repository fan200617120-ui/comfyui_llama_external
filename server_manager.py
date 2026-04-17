import subprocess
import time
import requests
import atexit
import os
import sys
import threading
import signal
from .common import friendly_error

ACTIVE_SERVERS = {}
SERVER_LOCK = threading.Lock()

def kill_process_on_port(port):
    """跨平台杀死占用指定端口的进程"""
    try:
        if sys.platform == "win32":
            # Windows: 使用 netstat + taskkill
            result = subprocess.run(
                f'netstat -ano | findstr :{port} | findstr LISTENING',
                shell=True, capture_output=True, text=True
            )
            lines = result.stdout.strip().split('\n')
            pids = set()
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid.isdigit():
                        pids.add(int(pid))
            for pid in pids:
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                print(f"[LLM External] 已强制杀死 PID {pid} (端口 {port})")
        else:
            # Linux/macOS: 使用 lsof 或 fuser
            for cmd in [f"lsof -ti :{port} | xargs kill -9 2>/dev/null", 
                        f"fuser -k {port}/tcp 2>/dev/null"]:
                result = subprocess.run(cmd, shell=True, capture_output=True)
                if result.returncode == 0:
                    print(f"[LLM External] 已杀死端口 {port} 的进程")
                    break
    except Exception as e:
        print(f"[LLM External] 杀死端口 {port} 进程时出错: {e}")

def cleanup_servers():
    """程序退出时清理所有托管的服务器进程"""
    with SERVER_LOCK:
        for url, proc in list(ACTIVE_SERVERS.items()):
            if proc and isinstance(proc, subprocess.Popen):
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except:
                    proc.kill()
        ACTIVE_SERVERS.clear()

atexit.register(cleanup_servers)

def kill_server(api_url=None, kill_all=False):
    global ACTIVE_SERVERS
    with SERVER_LOCK:
        if kill_all:
            for url, proc in list(ACTIVE_SERVERS.items()):
                if proc and isinstance(proc, subprocess.Popen):
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except:
                        proc.kill()
            ACTIVE_SERVERS.clear()
            return "已杀死所有外部 LLM 进程"
        elif api_url and api_url in ACTIVE_SERVERS:
            proc = ACTIVE_SERVERS[api_url]
            if proc and isinstance(proc, subprocess.Popen):
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except:
                    proc.kill()
            del ACTIVE_SERVERS[api_url]
            return f"已杀死进程: {api_url}"
    return "未找到对应的进程"

def get_running_model_at_port(port):
    """查询端口上运行的模型名称"""
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
    """启动或复用 llama-server 进程"""
    api_url = f"http://127.0.0.1:{port}/v1"
    expected_model_name = os.path.splitext(os.path.basename(model_path))[0]
    
    if force_reload:
        kill_process_on_port(port)
        with SERVER_LOCK:
            if api_url in ACTIVE_SERVERS:
                proc = ACTIVE_SERVERS[api_url]
                if proc and isinstance(proc, subprocess.Popen):
                    try:
                        proc.terminate()
                        proc.wait(timeout=2)
                    except:
                        proc.kill()
                del ACTIVE_SERVERS[api_url]
        time.sleep(2)

    # 检查端口是否已有兼容模型在运行
    running_model = get_running_model_at_port(port)
    if running_model is not None:
        if running_model.lower() == expected_model_name.lower():
            print(f"[LLM External] 端口 {port} 已有模型 {running_model} 在运行，直接复用。")
            with SERVER_LOCK:
                # 记录为外部进程，不清理
                ACTIVE_SERVERS[api_url] = "external"
            return api_url, running_model, None
        else:
            return None, None, f"错误：端口 {port} 已被模型 '{running_model}' 占用，与期望的 '{expected_model_name}' 不一致。\n解决方法：更换端口，或先杀死旧进程。"

    if not os.path.exists(exe_path):
        return None, None, f"错误：找不到 llama-server 可执行文件\n{exe_path}\n请确认路径是否正确。"

    # 命令行参数构建
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
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen(
                cmd,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Linux/macOS: 使用 preexec_fn 忽略 SIGHUP
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=lambda: signal.signal(signal.SIGHUP, signal.SIG_IGN)
            )
    except Exception as e:
        return None, None, f"启动 llama-server 失败: {e}"

    print(f"[LLM External] 等待模型加载 (端口 {port})...")
    for i in range(180):
        try:
            if requests.get(f"http://127.0.0.1:{port}/v1/models", timeout=2).status_code == 200:
                actual_model = get_running_model_at_port(port)
                if actual_model is None:
                    actual_model = expected_model_name
                print(f"[LLM External] 模型加载完成！实际模型名: {actual_model}")
                with SERVER_LOCK:
                    ACTIVE_SERVERS[api_url] = process
                return api_url, actual_model, None
        except:
            pass
        
        # 检查进程是否意外退出
        if process.poll() is not None:
            return None, None, f"错误：llama-server 启动后立即退出，可能是模型文件损坏或显存不足。"
        time.sleep(1)
    
    process.kill()
    return None, None, "错误：模型加载超时（3分钟），请检查模型大小或增加等待时间。"