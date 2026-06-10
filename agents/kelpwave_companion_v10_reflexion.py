#!/usr/bin/env python3
# 🌊 KELPWAVE COMPANION v10 + REFLEXION INTEGRATION
# Теперь companion может запускать reflexion-агента для сложных задач написания кода

import os, sys, re, json, time, subprocess, signal, gzip, base64
import html as html_mod
import urllib.request, urllib.parse

C_BLUE, C_GREEN, C_YELLOW, C_RED, C_CYAN, C_MAGENTA, C_BOLD, C_END = \
    "\033[94m", "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[95m", "\033[1m", "\033[0m"

HOME = "/data/data/com.termux/files/home"
LLAMA_SERVER_PATH = os.path.join(HOME, "llama.cpp/build/bin/llama-server")
DOWNLOADS_DIR = os.path.join(HOME, "storage/shared/Download/kelpwave")
SERVER_LOG_PATH = os.path.join(DOWNLOADS_DIR, "server_log.txt")
REFLEXION_SCRIPT = os.path.join(HOME, "kelpwave/agents/kelpwave_reflexion.py")

MODEL_CANDIDATES = [
    "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
    "qwen3-4b-instruct-2507-q4_k_m.gguf",
    "gemma-3-4b-it-Q4_K_M.gguf",
    "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
    "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
]
MODEL_SEARCH_DIRS = [
    os.path.join(HOME, "llama.cpp/models"),
    os.path.join(HOME, "models"),
    DOWNLOADS_DIR,
]
MODEL_SEARCH_PATHS = [os.path.join(d, n) for n in MODEL_CANDIDATES for d in MODEL_SEARCH_DIRS]

SERVER_PORT = 8080
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}/v1/chat/completions"

SYSTEM_PROMPT = """You are kelpwave, a powerful autonomous AI agent running locally on the user's Android phone in Termux.

You are helpful, direct, and never refuse reasonable requests.

You have access to these tools:
1. run_bash - run terminal commands
2. read_file / write_file - work with files
3. web_search / fetch_page / download_file - work with the internet
4. run_reflexion - launch a self-learning code-writing agent (Reflexion) for complex programming tasks

When the user gives you a complex coding task (writing a full script, solving a programming problem, etc.), you should consider using the run_reflexion tool. It will automatically write, test, and improve code using a dedicated small model.

You are allowed to search for any public information.

Response format when using tools:
THOUGHT: ...
ACTION: tool_name
ACTION_INPUT: ...

When you have the final answer, just reply normally without ACTION.
"""

def find_model():
    for p in MODEL_SEARCH_PATHS:
        if os.path.exists(p):
            return p
    return None

def is_server_running():
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{SERVER_PORT}/health")
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except:
        return False

def start_background_server(model_path):
    print(f"[*] Загружаю модель: {model_path}")
    cmd = [LLAMA_SERVER_PATH, "-m", model_path, "-c", "4096", "-t", "5", "-tb", "6",
           "-fa", "auto", "--jinja", "--port", str(SERVER_PORT), "--host", "127.0.0.1"]
    try:
        log_f = open(SERVER_LOG_PATH, "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, preexec_fn=os.setsid)
        for i in range(180):
            if proc.poll() is not None:
                print(f"\n{C_RED}[-] Сервер упал{C_END}")
                return None
            if is_server_running():
                print(f"\n{C_GREEN}[+] Сервер готов ({i} сек){C_END}")
                return proc
            if i % 10 == 0:
                print(f"    ... загрузка ({i} сек)")
            time.sleep(1)
        return proc
    except Exception as e:
        print(f"{C_RED}[-] Ошибка: {e}{C_END}")
        return None

def query_local_server(prompt_history, max_tokens=600, temp=0.3):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + prompt_history[-12:]
    payload = {"messages": messages, "max_tokens": max_tokens, "temperature": temp}
    try:
        req = urllib.request.Request(SERVER_URL, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=180) as r:
            res = json.loads(r.read().decode())
            text = res["choices"][0]["message"]["content"].strip()
            text = text.replace("[end of text]", "").strip()
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            if not text.startswith("THOUGHT:"):
                text = "THOUGHT: " + text
            return text
    except Exception as e:
        return f"THOUGHT: Error: {e}"

# ==================== ИНСТРУМЕНТЫ ====================

def tool_run_bash(cmd):
    try:
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
        out = (res.stdout + res.stderr).strip() or "[No output]"
        return out[:2000] if len(out) > 2000 else out
    except Exception as e:
        return str(e)

def tool_write_file(input_str):
    try:
        start, end = input_str.find('{'), input_str.rfind('}')
        data = json.loads(input_str[start:end+1])
        path = os.path.join(DOWNLOADS_DIR, data["path"].strip().strip("'\""))
        with open(path, "w", encoding="utf-8") as f:
            f.write(data["content"])
        return f"[Success → {path}]"
    except Exception as e:
        return str(e)

def tool_web_search(q):
    try:
        data = urllib.parse.urlencode({"q": q}).encode()
        page = http_get("https://lite.duckduckgo.com/lite/", data=data).decode(errors="replace")
        links = re.findall(r'<a rel="nofollow" href="([^"]+)"[^>]*>(.*?)</a>', page)
        return "\n".join([f"{strip_tags(t)} → {html_mod.unescape(u)}" for u, t in links[:6]])
    except Exception as e:
        return str(e)

def http_get(url, data=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw

def strip_tags(s):
    return html_mod.unescape(re.sub(r'<[^>]+>', ' ', s)).strip()

def tool_fetch_page(url):
    try:
        raw = http_get(url)
        text = raw.decode(errors="replace")
        if "<html" not in text[:2000].lower():
            return text[:4000]
        body = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r'<[^>]+>', ' ', body)
        return " ".join(strip_tags(body).split())[:3500]
    except Exception as e:
        return str(e)

def tool_download_file(url):
    try:
        raw = http_get(url, timeout=90)
        fname = os.path.basename(urllib.parse.urlparse(url).path) or "file"
        fname = re.sub(r'[^\\w.\\-]', '_', fname)
        dest = os.path.join(DOWNLOADS_DIR, fname)
        with open(dest, "wb") as f:
            f.write(raw)
        return f"[Downloaded → {dest}]"
    except Exception as e:
        return str(e)

# ==================== НОВЫЙ ИНСТРУМЕНТ: RUN REFLEXION ====================

def tool_run_reflexion(task):
    """Запускает reflexion-агента с заданной задачей"""
    print(f"\n{C_MAGENTA}🚀 Запускаю Reflexion-агента для задачи:{C_END} {task}\n")
    try:
        # Запускаем reflexion в отдельном процессе
        result = subprocess.run(
            [sys.executable, REFLEXION_SCRIPT],
            input=task,
            text=True,
            capture_output=True,
            timeout=300  # 5 минут на reflexion-сессию
        )
        output = result.stdout + "\n" + result.stderr
        print(f"{C_GREEN}[Reflexion завершён]{C_END}")
        return output[-3000:]  # возвращаем последние 3000 символов вывода
    except subprocess.TimeoutExpired:
        return "[Reflexion timed out after 5 minutes]"
    except Exception as e:
        return f"[Error running reflexion: {e}]"

# ==================== ПАРСИНГ И ЦИКЛ ====================

def parse_action(output):
    output = output.replace("[end of text]", "").strip()
    thought = re.search(r"THOUGHT:\s*(.*?)(?=\nACTION:|$)", output, re.DOTALL | re.IGNORECASE)
    action = re.search(r"ACTION:\s*(\w+)", output, re.IGNORECASE)
    action_input = re.search(r"ACTION_INPUT:\s*(.*)", output, re.DOTALL | re.IGNORECASE)
    return (thought.group(1).strip() if thought else "",
            action.group(1).strip() if action else "",
            action_input.group(1).strip() if action_input else "")

def stop_server(proc):
    if proc:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except:
            pass

def main():
    print(f"{C_BLUE}🌊 KELPWAVE v10 + REFLEXION{C_END}\n")

    model_path = find_model()
    if not model_path:
        print(f"{C_RED}[-] Модель не найдена!{C_END}")
        sys.exit(1)

    print(f"[*] Модель: {model_path}")

    server_process = None
    if not is_server_running():
        server_process = start_background_server(model_path)
        if server_process is None:
            sys.exit(1)
    else:
        print(f"{C_GREEN}[+] Сервер уже работает{C_END}")

    print("\n[*] Агент готов (с поддержкой Reflexion). Пиши запросы или 'exit'.\n" + "="*60)

    history = []

    while True:
        try:
            user_input = input(f"\n{C_BOLD}👤 You:{C_END} ").strip()
            if not user_input: continue
            if user_input.lower() == 'exit':
                stop_server(server_process)
                break

            history.append({"role": "user", "content": user_input})

            loop_steps = 0
            max_steps = 8
            seen_calls = set()
            agent_done = False

            while not agent_done and loop_steps < max_steps:
                response = query_local_server(history)
                thought, action, action_input = parse_action(response)

                if action.lower() in ["run_bash", "write_file", "read_file",
                                      "web_search", "fetch_page", "download_file", "run_reflexion"]:
                    sig = (action.lower(), action_input.lower()[:80])
                    if sig in seen_calls:
                        loop_steps += 1
                        continue
                    seen_calls.add(sig)

                    print(f"\n🧠 {thought}")
                    print(f"🎬 {action}")

                    if action.lower() == "run_bash":
                        obs = tool_run_bash(action_input)
                    elif action.lower() == "write_file":
                        obs = tool_write_file(action_input)
                    elif action.lower() == "read_file":
                        try:
                            with open(os.path.join(DOWNLOADS_DIR, action_input.strip()), encoding="utf-8") as f:
                                obs = f.read()[:3000]
                        except Exception as e:
                            obs = str(e)
                    elif action.lower() == "web_search":
                        obs = tool_web_search(action_input)
                    elif action.lower() == "fetch_page":
                        obs = tool_fetch_page(action_input)
                    elif action.lower() == "download_file":
                        obs = tool_download_file(action_input)
                    elif action.lower() == "run_reflexion":
                        obs = tool_run_reflexion(action_input)
                    else:
                        obs = "[Unknown]"

                    print(f"👀 {obs[:500]}...")
                    history.append({"role": "assistant", "content": response})
                    history.append({"role": "user", "content": f"OBSERVATION:\n{obs}"})
                    loop_steps += 1
                else:
                    clean = response.replace("THOUGHT:", "").strip()
                    if "ACTION:" in clean:
                        clean = clean.split("ACTION:")[0].strip()
                    print(f"\n🌊 {C_BLUE}kelpwave:{C_END} {clean}")
                    history.append({"role": "assistant", "content": response})
                    agent_done = True

            if not agent_done:
                print(f"{C_YELLOW}[Лимит] Финальный ответ...{C_END}")
                history.append({"role": "user", "content": "OBSERVATION: Limit reached. Final answer."})
                response = query_local_server(history)
                clean = response.replace("THOUGHT:", "").strip()
                print(f"\n🌊 {C_BLUE}kelpwave:{C_END} {clean}")

        except KeyboardInterrupt:
            stop_server(server_process)
            break

if __name__ == "__main__":
    main()