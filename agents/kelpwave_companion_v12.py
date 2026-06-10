#!/usr/bin/env python3
# 🌊 KELPWAVE v12 — SELF-IMPROVING + ALL GUARDS RESTORED
# Слияние v9 (Loop Guard, URL Guard, fetch_page с ссылками, бан pkg install)
# + v11 (долгосрочная память, авто-обучение, reflexion)
# + v10 (свободный промпт)

import os, sys, re, json, time, subprocess, signal, gzip, base64
import html as html_mod
import urllib.request, urllib.parse

# Импортируем систему памяти
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "tools"))
from memory import load_lessons, save_lessons, add_lesson, get_lessons_context

C_BLUE, C_GREEN, C_YELLOW, C_RED, C_CYAN, C_MAGENTA, C_BOLD, C_END = \
    "\033[94m", "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[95m", "\033[1m", "\033[0m"

HOME = "/data/data/com.termux/files/home"
LLAMA_SERVER_PATH = os.path.join(HOME, "llama.cpp/build/bin/llama-server")
DOWNLOADS_DIR = os.path.join(HOME, "storage/shared/Download/kelpwave")
SERVER_LOG_PATH = os.path.join(DOWNLOADS_DIR, "server_log.txt")

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

SYSTEM_PROMPT_BASE = """You are kelpwave, a self-improving autonomous AI agent running locally on the user's Android phone in Termux.

You learn from your past mistakes and become better over time. Lessons from previous failures are injected into your prompt.

You are helpful, direct, and never refuse reasonable requests. You can search the web, read/write files, run terminal commands, download files, and launch reflexion for coding tasks.

You are allowed to:
- Search for any public information (including usernames, nicknames, public profiles)
- Download any publicly available files
- Execute terminal commands
- Write files

Only refuse if the request is clearly illegal or extremely harmful.

YOUR ENVIRONMENT (already set up):
- Termux home: /data/data/com.termux/files/home
- Shared folder (user-visible): /sdcard/Download/kelpwave
- Storage access ALREADY granted. NEVER run termux-setup-storage.
- Packages ALREADY installed. NEVER run pkg install/apt install/pkg upgrade.
- python3, git, curl, wget are available.

TOOL RULES:
- To find something: FIRST web_search with simple keywords, THEN use URLs from results.
- NEVER invent URLs. Use ONLY URLs from web_search results or user messages.
- For GitHub files, use raw.githubusercontent.com URLs.
- download_file works ONLY with DIRECT file links (ending .txt/.zip/.pdf/.md etc).
- To ask user something, reply in plain text WITHOUT ACTION. NEVER use run_bash echo to ask.

Response format when using tools:
THOUGHT: ...
ACTION: tool_name
ACTION_INPUT: ...

When finished, reply normally without ACTION.
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

def tail_server_log(n=15):
    try:
        with open(SERVER_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:])
    except:
        return "(лог недоступен)"

def start_background_server(model_path):
    print(f"[*] Загружаю модель: {model_path}")
    if "/sdcard/" in model_path:
        print(f"{C_YELLOW}[!] Модель на /sdcard — медленно. Перенеси в ~/llama.cpp/models/{C_END}")
    cmd = [LLAMA_SERVER_PATH, "-m", model_path, "-c", "4096", "-t", "5", "-tb", "6",
           "-fa", "auto", "--jinja", "--port", str(SERVER_PORT), "--host", "127.0.0.1"]
    try:
        log_f = open(SERVER_LOG_PATH, "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, preexec_fn=os.setsid)
        for i in range(180):
            if proc.poll() is not None:
                print(f"\n{C_RED}[-] Сервер упал{C_END}\n{tail_server_log()}")
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

def query_local_server(prompt_history, max_tokens=650, temp=0.3):
    lessons_text = get_lessons_context(max_lessons=6)
    full_system = SYSTEM_PROMPT_BASE + lessons_text
    messages = [{"role": "system", "content": full_system}] + prompt_history[-12:]
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
WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"

def http_get(url, data=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": WEB_UA, "Accept": "text/html,*/*", "Accept-Encoding": "gzip"
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw

def strip_tags(s):
    return html_mod.unescape(re.sub(r'<[^>]+>', ' ', s)).strip()

def clean_tool_input(s):
    return s.replace("[end of text]", "").replace("<|im_end|>", "").strip().strip("'\"")

def tool_run_bash(command):
    clean = clean_tool_input(command)
    BANNED = ["pkg install", "apt install", "pkg upgrade", "apt upgrade",
              "apt-get install", "termux-setup-storage", "pkg update"]
    for b in BANNED:
        if b in clean:
            return f"[BLOCKED: '{b}' запрещён. Окружение уже настроено.]"
    try:
        res = subprocess.run(clean, shell=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, timeout=90)
        out = (res.stdout + res.stderr).strip() or "[No output]"
        return out[:1500] + f"\n... [truncated]" if len(out) > 1500 else out
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

def _decode_bing_url(u):
    u = html_mod.unescape(u)
    m = re.search(r'[?&]u=a1([^&]+)', u)
    if not m: return u
    b64 = m.group(1) + "=" * (-len(m.group(1)) % 4)
    try: return base64.urlsafe_b64decode(b64).decode("utf-8", errors="replace")
    except: return u

def _search_ddg_lite(query, n=5):
    data = urllib.parse.urlencode({"q": query}).encode()
    page = http_get("https://lite.duckduckgo.com/lite/", data=data).decode(errors="replace")
    if "confirm" in page: return []
    links = re.findall(r'<a rel="nofollow" href="([^"]+)"[^>]*>(.*?)</a>', page)
    return [f"Title: {strip_tags(t)}\nURL: {html_mod.unescape(u)}\n" for u, t in links[:n]]

def _search_bing(query, n=5):
    url = "https://www.bing.com/search?q=" + urllib.parse.quote_plus(query)
    page = http_get(url).decode(errors="replace")
    blocks = re.findall(r'<li class="b_algo".*?</li>', page, re.DOTALL)
    results = []
    for b in blocks[:n]:
        m = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', b, re.DOTALL)
        if not m: continue
        results.append(f"Title: {strip_tags(m.group(2))}\nURL: {_decode_bing_url(m.group(1))}\n")
    return results

def tool_web_search(q):
    clean_q = clean_tool_input(q)
    for name, fn in [("DuckDuckGo", _search_ddg_lite), ("Bing", _search_bing)]:
        try:
            res = fn(clean_q)
            if res:
                return f"[{name}]\n" + "\n".join(res) + "\n[SYSTEM] Next: pick ONE URL and use fetch_page or download_file."
        except: pass
    return "[No results]"

def tool_fetch_page(url):
    clean_url = clean_tool_input(url)
    try:
        raw = http_get(clean_url)
        text = raw.decode(errors="replace")
        if "<html" not in text[:2000].lower():
            return text[:3000]
        # Собираем ссылки ДО очистки
        links = []
        seen = set()
        for m in re.finditer(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', text, re.DOTALL | re.IGNORECASE):
            href = html_mod.unescape(m.group(1).strip())
            abs_url = urllib.parse.urljoin(clean_url, href)
            if abs_url.startswith("http") and abs_url not in seen:
                seen.add(abs_url)
                label = strip_tags(m.group(2))[:60]
                links.append((abs_url, label))
        FILE_EXT = re.compile(r'\.(txt|zip|pdf|json|csv|md|xml|gguf|tar|gz|7z|docx|xlsx|png|jpg|mp3|wav)([?#]|$)', re.I)
        file_links = [l for l in links if FILE_EXT.search(l[0])]
        body = re.sub(r'<script.*?</script>|<style.*?</style>', '', text, flags=re.DOTALL | re.I)
        body = " ".join(strip_tags(body).split())
        out = body[:1800]
        if file_links:
            out += "\n\n=== DIRECT FILE LINKS (use with download_file!) ===\n" + "\n".join(f"- {u} ({l})" for u,l in file_links[:15])
        return out
    except Exception as e:
        return str(e)

def tool_download_file(url):
    clean_url = clean_tool_input(url)
    m = re.match(r'https://github\.com/([^/]+)/([^/]+)/blob/(.+)', clean_url)
    if m: clean_url = f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}"
    try:
        raw = http_get(clean_url, timeout=90)
        head = raw[:2000].decode(errors="replace").lower()
        if "<!doctype html" in head or "<html" in head:
            return "[Error: URL is HTML page, not file. Find direct link ending .txt/.zip etc.]"
        fname = re.sub(r'[^\w.\-]', '_', os.path.basename(urllib.parse.urlparse(clean_url).path) or "file")
        dest = os.path.join(DOWNLOADS_DIR, fname)
        with open(dest, "wb") as f: f.write(raw)
        return f"[Downloaded → {dest}]"
    except Exception as e:
        return str(e)

def tool_run_reflexion(task):
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(HOME, "kelpwave/agents/kelpwave_reflexion.py")],
            input=task, text=True, capture_output=True, timeout=300
        )
        return (result.stdout + result.stderr)[-3000:]
    except Exception as e:
        return f"[Error: {e}]"

# URL Guard
URL_RE = re.compile(r'https?://[^\s"\'<>\\)\]]+')
def extract_urls(text): return set(u.rstrip('.,;:!?') for u in URL_RE.findall(text or ""))
def url_exists(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": WEB_UA})
        with urllib.request.urlopen(req, timeout=8) as r: return 200 <= r.status < 400
    except: return False

def parse_action(output):
    output = output.replace("[end of text]", "").strip()
    t = re.search(r"THOUGHT:\s*(.*?)(?=\nACTION:|$)", output, re.DOTALL | re.I)
    a = re.search(r"ACTION:\s*(\w+)", output, re.I)
    ai = re.search(r"ACTION_INPUT:\s*(.*)", output, re.DOTALL | re.I)
    return (t.group(1).strip() if t else "", a.group(1).strip() if a else "", ai.group(1).strip() if ai else "")

def stop_server(proc):
    if proc:
        try: os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except: pass

def main():
    print(f"{C_BLUE}🌊 KELPWAVE v12 — SELF-IMPROVING + GUARDS{C_END}\n")
    model_path = find_model()
    if not model_path:
        print(f"{C_RED}[-] Модель не найдена{C_END}"); sys.exit(1)
    print(f"[*] Модель: {model_path}")
    server_proc = None
    if not is_server_running():
        server_proc = start_background_server(model_path)
        if not server_proc: sys.exit(1)
    else: print(f"{C_GREEN}[+] Сервер уже работает{C_END}")

    lessons = load_lessons()
    print(f"[*] Загружено уроков из памяти: {len(lessons)}")
    print("[*] Агент готов. 'exit' для выхода.\n" + "="*60)

    history = []
    while True:
        try:
            user_input = input(f"\n{C_BOLD}👤 You:{C_END} ").strip()
            if not user_input: continue
            if user_input.lower() == 'exit':
                stop_server(server_proc); break
            history.append({"role": "user", "content": user_input})
            loop_steps, max_steps = 0, 8
            seen_calls, repeat_strikes = set(), 0
            known_urls = extract_urls(user_input)
            agent_done = False

            while not agent_done and loop_steps < max_steps:
                response = query_local_server(history)
                thought, action, action_input = parse_action(response)
                action_l = action.lower()

                if action_l in ["run_bash","write_file","read_file","web_search","fetch_page","download_file","run_reflexion"]:
                    sig = (action_l, action_input.lower()[:100])
                    if sig in seen_calls:
                        repeat_strikes += 1
                        print(f"{C_YELLOW}[LOOP GUARD] Повтор {action}{C_END}")
                        if repeat_strikes >= 2:
                            history.append({"role":"assistant","content":response})
                            history.append({"role":"user","content":"OBSERVATION:\n[SYSTEM] Loop detected. Stop tools. Give final answer now."})
                            response = query_local_server(history)
                            print(f"\n🌊 kelpwave: {response.replace('THOUGHT:','').split('ACTION:')[0]}")
                            agent_done = True; break
                        loop_steps += 1; continue
                    seen_calls.add(sig)

                    # URL Guard
                    if action_l in ("fetch_page","download_file"):
                        cand = clean_tool_input(action_input)
                        if cand.startswith("http") and cand not in known_urls:
                            print(f"{C_YELLOW}[URL GUARD] Проверяю {cand[:60]}...{C_END}")
                            if url_exists(cand):
                                known_urls.add(cand)
                            else:
                                obs = f"[BLOCKED] URL не существует. Используй только URL из web_search. Известные: {list(known_urls)[:5]}"
                                history.append({"role":"assistant","content":response})
                                history.append({"role":"user","content":f"OBSERVATION:\n{obs}"})
                                loop_steps += 1; continue

                    print(f"\n🧠 {thought}\n🎬 {action}")
                    if action_l == "run_bash": obs = tool_run_bash(action_input)
                    elif action_l == "write_file": obs = tool_write_file(action_input)
                    elif action_l == "read_file":
                        try: obs = open(os.path.join(DOWNLOADS_DIR, action_input.strip()), encoding="utf-8").read()[:3000]
                        except Exception as e: obs = str(e)
                    elif action_l == "web_search": obs = tool_web_search(action_input)
                    elif action_l == "fetch_page": obs = tool_fetch_page(action_input)
                    elif action_l == "download_file": obs = tool_download_file(action_input)
                    elif action_l == "run_reflexion": obs = tool_run_reflexion(action_input)
                    else: obs = "[Unknown]"

                    print(f"👀 {obs[:400]}...")
                    known_urls |= extract_urls(obs)

                    # Авто-обучение
                    if any(w in obs.lower() for w in ["error","failed","exception","timeout","not found","blocked","404"]):
                        add_lesson(f"When using {action}, got: {obs[:120]}", context=user_input)

                    history.append({"role":"assistant","content":response})
                    history.append({"role":"user","content":f"OBSERVATION:\n{obs}"})
                    loop_steps += 1
                else:
                    clean = response.replace("THOUGHT:","").split("ACTION:")[0].strip()
                    print(f"\n🌊 {C_BLUE}kelpwave:{C_END} {clean}")
                    history.append({"role":"assistant","content":response})
                    agent_done = True

            if not agent_done:
                history.append({"role":"user","content":"OBSERVATION: Limit reached. Final answer."})
                response = query_local_server(history)
                print(f"\n🌊 kelpwave: {response.replace('THOUGHT:','').split('ACTION:')[0]}")

        except KeyboardInterrupt:
            stop_server(server_proc); break

if __name__ == "__main__":
    main()