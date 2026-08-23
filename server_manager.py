import subprocess
import time
import requests
import atexit
import os
import sys
import threading
import signal
import re
import shutil

ACTIVE_SERVERS = {}
SERVER_CONFIGS = {}  # 修复 #2：api_url -> 配置签名
SERVER_LOCK = threading.Lock()


def kill_process_on_port(port):
    """跨平台杀死占用指定端口的进程（修复 #21：增加 LISTEN 过滤）"""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                f'netstat -ano | findstr :{port} | findstr LISTENING',
                shell=True, capture_output=True, text=True
            )
            lines = result.stdout.strip().split('\n')
            pids = set()
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 5 and parts[1].endswith(f':{port}'):
                    pid = parts[-1]
                    if pid.isdigit():
                        pids.add(int(pid))
            for pid in pids:
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                print(f"[LLM External] 已强制杀死 PID {pid} (端口 {port})")
        else:
            # 修复 #21：只杀 LISTEN 状态，避免误杀连接到远程端口的进程
            for cmd in [
                f"lsof -ti :{port} -sTCP:LISTEN | xargs kill -9 2>/dev/null",
                f"fuser -k {port}/tcp 2>/dev/null"
            ]:
                result = subprocess.run(cmd, shell=True, capture_output=True)
                if result.returncode == 0:
                    print(f"[LLM External] 已杀死端口 {port} 的进程")
                    break
    except Exception as e:
        print(f"[LLM External] 杀死端口 {port} 进程时出错: {e}")


def cleanup_servers():
    """程序退出时清理所有托管的服务器进程"""
    with SERVER_LOCK:
        to_delete = []
        for url, proc in list(ACTIVE_SERVERS.items()):
            if proc and isinstance(proc, subprocess.Popen):
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except Exception as e:
                        print(f"[LLM External] 强制杀死进程失败: {e}")
                except Exception as e:
                    print(f"[LLM External] 清理进程异常: {e}")
            to_delete.append(url)
        for url in to_delete:
            ACTIVE_SERVERS.pop(url, None)
            SERVER_CONFIGS.pop(url, None)


atexit.register(cleanup_servers)


def kill_server(api_url=None, kill_all=False):
    """杀死指定或所有外部 LLM 服务进程（修复 #3：处理 external 记录）"""
    global ACTIVE_SERVERS, SERVER_CONFIGS
    with SERVER_LOCK:
        if kill_all:
            to_delete = []
            for url, proc in list(ACTIVE_SERVERS.items()):
                if proc and isinstance(proc, subprocess.Popen):
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        try:
                            proc.kill()
                        except Exception as e:
                            print(f"[LLM External] 强制杀死进程失败: {e}")
                    except Exception as e:
                        print(f"[LLM External] 终止进程异常: {e}")
                elif proc == "external":
                    # 修复 #3：external 记录按端口强杀
                    m = re.search(r':(\d+)', url or "")
                    if m:
                        kill_process_on_port(int(m.group(1)))
                to_delete.append(url)
            for url in to_delete:
                ACTIVE_SERVERS.pop(url, None)
                SERVER_CONFIGS.pop(url, None)
            return "已杀死所有外部 LLM 进程"
        
        elif api_url:
            # 标准化 URL
            api_url = api_url.rstrip('/')
            if api_url.endswith('/v1'):
                api_url = api_url[:-3]
            if not api_url.startswith('http'):
                api_url = f'http://{api_url}'
            
            if api_url in ACTIVE_SERVERS:
                proc = ACTIVE_SERVERS.pop(api_url, None)
                SERVER_CONFIGS.pop(api_url, None)
                if proc and isinstance(proc, subprocess.Popen):
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        try:
                            proc.kill()
                        except Exception as e:
                            print(f"[LLM External] 强制杀死进程失败: {e}")
                    except Exception as e:
                        print(f"[LLM External] 终止进程异常: {e}")
                    return f"已杀死进程: {api_url}"
                elif proc == "external":
                    # external 记录：按端口强杀
                    m = re.search(r':(\d+)', api_url or "")
                    if m:
                        kill_process_on_port(int(m.group(1)))
                        return f"已强制杀死端口 {m.group(1)} 上的外部进程"
                    return f"已清理 external 记录: {api_url}"
            else:
                # 不在托管列表中，尝试按端口强杀
                m = re.search(r':(\d+)', api_url or "")
                if m:
                    kill_process_on_port(int(m.group(1)))
                    return f"已强制杀死端口 {m.group(1)} 上的进程"
                return "未找到对应的进程"
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
    except (requests.RequestException, requests.JSONDecodeError):
        pass
    except Exception as e:
        print(f"[LLM External] 查询端口 {port} 模型异常: {e}")
    return None


def start_llama_server(exe_path, model_path, mmproj_path, port, gpu_layers, ctx_size, 
                       force_reload=False, 
                       cache_type_k="f16", cache_type_v="f16",
                       cpu_moe=False, n_cpu_moe=0):
    """
    启动或复用 llama-server 进程（修复 #2：配置签名比较）
    """
    api_url = f"http://127.0.0.1:{port}/v1"
    expected_model_name = os.path.splitext(os.path.basename(model_path))[0]
    
    # 计算配置签名
    new_sig = f"{model_path}|{mmproj_path}|{ctx_size}|{gpu_layers}|{cache_type_k}|{cache_type_v}|{cpu_moe}|{n_cpu_moe}"
    
    # 检查是否可复用（修复 #2）
    if not force_reload:
        with SERVER_LOCK:
            proc = ACTIVE_SERVERS.get(api_url)
            old_sig = SERVER_CONFIGS.get(api_url)
        
        # 进程活着且配置完全一致 → 直接复用
        if (proc and isinstance(proc, subprocess.Popen) and proc.poll() is None
                and old_sig == new_sig):
            print(f"[LLM External] 端口 {port} 已有配置一致的模型在运行，直接复用。")
            return api_url, expected_model_name, None
        
        # 配置不同但有进程在运行 → 需要重启
        if proc and isinstance(proc, subprocess.Popen) and proc.poll() is None:
            print(f"[LLM External] 配置已变更，正在重启服务...")
            with SERVER_LOCK:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                except Exception:
                    pass
                ACTIVE_SERVERS.pop(api_url, None)
                SERVER_CONFIGS.pop(api_url, None)
            time.sleep(1)

    # 检测端口上的其他进程
    running_model = get_running_model_at_port(port)
    if running_model is not None:
        if running_model.lower() == expected_model_name.lower():
            print(f"[LLM External] 端口 {port} 已有模型 {running_model} 在运行，直接复用。")
            with SERVER_LOCK:
                ACTIVE_SERVERS[api_url] = "external"
                SERVER_CONFIGS[api_url] = new_sig
            return api_url, running_model, None
        else:
            return None, None, f"错误：端口 {port} 已被模型 '{running_model}' 占用，与期望的 '{expected_model_name}' 不一致。\n解决方法：更换端口，或先杀死旧进程。"

    # 验证 exe_path
    if not os.path.exists(exe_path):
        # 尝试从 PATH 查找
        found = shutil.which("llama-server")
        if found:
            exe_path = found
        else:
            return None, None, f"错误：找不到 llama-server 可执行文件\n{exe_path}\n请确认路径是否正确，或安装 llama.cpp。"

    cmd = [
        exe_path,
        "-m", model_path,
        "-c", str(ctx_size),
        "-ngl", str(gpu_layers),
        "--port", str(port),
        "--host", "127.0.0.1"
    ]
    if mmproj_path and mmproj_path.strip() and os.path.exists(mmproj_path.strip()):
        cmd.extend(["--mmproj", mmproj_path.strip()])
    
    if cache_type_k and cache_type_k != "f16":
        cmd.extend(["--cache-type-k", cache_type_k])
    if cache_type_v and cache_type_v != "f16":
        cmd.extend(["--cache-type-v", cache_type_v])
    
    if cpu_moe:
        cmd.append("--cpu-moe")
    elif n_cpu_moe > 0:
        cmd.extend(["--num-cpu-moe", str(n_cpu_moe)])

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
            # 修复 #21：移除 preexec_fn（多线程环境下有死锁风险）
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
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
                    SERVER_CONFIGS[api_url] = new_sig
                return api_url, actual_model, None
        except (requests.RequestException, requests.JSONDecodeError):
            pass
        except Exception as e:
            print(f"[LLM External] 检查模型状态异常: {e}")

        returncode = process.poll()
        if returncode is not None:
            with SERVER_LOCK:
                ACTIVE_SERVERS.pop(api_url, None)
                SERVER_CONFIGS.pop(api_url, None)
            return None, None, f"错误：llama-server 启动后立即退出（返回码: {returncode}），可能是模型文件损坏、显存不足或配置错误。"
        time.sleep(1)

    try:
        process.terminate()
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
    except Exception as e:
        print(f"[LLM External] 清理超时进程异常: {e}")

    with SERVER_LOCK:
        ACTIVE_SERVERS.pop(api_url, None)
        SERVER_CONFIGS.pop(api_url, None)
    return None, None, "错误：模型加载超时（3分钟），请检查模型大小、显存或网络连接。"


# ==================== 根据 API URL 卸载服务（修复 #4） ====================
def unload_by_api_url(api_url):
    """
    根据 API URL 卸载服务（杀死对应端口的进程）
    返回 (成功信息, 错误信息)
    """
    if not api_url:
        return None, "API URL 为空"
    
    # 标准化 API URL
    api_url = api_url.rstrip('/')
    if api_url.endswith('/v1'):
        api_url = api_url[:-3]
    if not api_url.startswith('http'):
        api_url = f'http://{api_url}'
    
    # 提取端口
    match = re.search(r':(\d+)(?:/|$)', api_url)
    if not match:
        return None, f"无法从 API URL 提取端口: {api_url}"
    port = int(match.group(1))
    
    with SERVER_LOCK:
        # 检查是否有托管记录
        if api_url in ACTIVE_SERVERS:
            proc = ACTIVE_SERVERS.pop(api_url, None)
            SERVER_CONFIGS.pop(api_url, None)
            if proc and isinstance(proc, subprocess.Popen):
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                except Exception as e:
                    return None, f"终止进程失败: {e}"
                return f"已终止端口 {port} 的托管进程", None
            elif proc == "external":
                # 外部进程：强杀
                kill_process_on_port(port)
                return f"已强制杀死端口 {port} 上的外部进程", None
        else:
            # 无托管记录，但可能仍有进程占用端口
            kill_process_on_port(port)
            # 修复 #4：清理可能的陈旧记录
            ACTIVE_SERVERS.pop(api_url, None)
            SERVER_CONFIGS.pop(api_url, None)
            return f"已强制杀死端口 {port} 上的进程", None
    
    return None, f"未能找到端口 {port} 的进程"