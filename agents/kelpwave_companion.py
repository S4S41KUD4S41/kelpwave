#!/usr/bin/env python3
# 🌊 KELPWAVE ULTIMATE COMPANION v9 — model-agnostic + паспорт окружения
# Изменения относительно v8:
#  [NEW] МОДЕЛЕНЕЗАВИСИМОСТЬ: переход на /v1/chat/completions + --jinja.
#        llama-server сам применяет родной шаблон модели. Теперь работают
#        Qwen, Gemma, Llama и любые другие GGUF без правки кода.
#  [NEW] Паспорт окружения в промпте: агент знает свои пути (Downloads,
#        home), что storage уже настроен, и что pkg install уже не нужен.
#  [FIX] run_bash: бан тяжёлых команд (pkg install/upgrade, termux-setup-storage)
#        во время работы — они душат CPU (таймауты модели) и переполняют
#        контекст выводом. Всё нужное ставится заранее через tools/setup.sh.
#  [FIX] run_bash: вывод обрезается до 1500 символов (защита контекста).
#  [NEW] tools/setup.sh — предустановка всего окружения одной командой.
# Изменения v8 (сохранены):
#  [FIX] fetch_page возвращает текст + список ссылок (прямые файловые отдельно)
# Изменения v7 (сохранены):
#  [FIX] URL Guard стал умным: выдуманный URL теперь не блокируется вслепую,
#        а ПРОВЕРЯЕТСЯ реальным HEAD-запросом. Существует — разрешаем,
#        нет — блокируем. (Раньше блокировались даже правильные догадки.)
#  [NEW] Поддержка Qwen3-4B-Instruct-2507 как основной модели (агентная,
#        меньше и быстрее 7B Coder). Автовыбор: Qwen3 если скачана, иначе 7B.
#        Скачать: см. tools/doctor.py или README.
#  [FIX] Запрещено "спрашивать пользователя" через run_bash echo — модель
#        теперь отвечает пользователю напрямую, если нужно уточнение.
# Изменения v6 (сохранены):
#  [FIX] download_file отклоняет HTML-страницы вместо "скачивания" их
# Изменения v5 (сохранены):
#  [NEW] URL Guard: модель часто галлюцинирует несуществующие ссылки (HTTP 404).
#        Теперь download_file/fetch_page принимают только URL, которые реально
#        встречались в результатах поиска или сообщениях пользователя.
#        При блокировке модели показывается список НАСТОЯЩИХ доступных URL.
#  [FIX] После ошибки 404 модель получает явное указание не выдумывать ссылки.
# Изменения v4 (сохранены):
#  [FIX] Loop Guard: повтор того же инструмента с тем же входом блокируется
#  [FIX] Принудительный финальный ответ при исчерпании лимита шагов
# Изменения v3 (сохранены):
#  [FIX] web_search через lite.duckduckgo.com + запасной Bing (вместо капчи)
#  [FIX] fetch_page: gzip, raw-файлы, лимит 3000 символов
#  [NEW] download_file с автоконверсией github blob -> raw
# Изменения v2 (сохранены):
#  [FIX] -fa auto, лог сервера в server_log.txt, убран --mlock,
#        ожидание 180 сек, проверки модели/бинарника до старта, автопоиск модели

import os, sys, re, json, time, subprocess, signal, gzip, base64
import html as html_mod
import urllib.request, urllib.parse

C_BLUE, C_GREEN, C_YELLOW, C_RED, C_CYAN, C_MAGENTA, C_BOLD, C_END = "\033[94m", "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[95m", "\033[1m", "\033[0m"

# ---------- Пути ----------
HOME = "/data/data/com.termux/files/home"
LLAMA_SERVER_PATH = os.path.join(HOME, "llama.cpp/build/bin/llama-server")
DOWNLOADS_DIR = os.path.join(HOME, "storage/shared/Download/kelpwave")
SERVER_LOG_PATH = os.path.join(DOWNLOADS_DIR, "server_log.txt")

# v7: приоритет — агентная Qwen3-4B (новее, меньше, лучше следует инструкциям),
# затем привычная 7B Coder. Ищем в домашней папке (быстро) и на /sdcard.
# v9: благодаря --jinja работает любая модель. Порядок = приоритет.
MODEL_CANDIDATES = [
    "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
    "qwen3-4b-instruct-2507-q4_k_m.gguf",
    "gemma-3-4b-it-Q4_K_M.gguf",                # Google Gemma 3 (альтернатива)
    "Llama-3.2-3B-Instruct-Q4_K_M.gguf",        # Meta Llama 3.2 (легче, 1.9 ГБ)
    "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
]
MODEL_SEARCH_DIRS = [
    os.path.join(HOME, "llama.cpp/models"),
    os.path.join(HOME, "models"),
    DOWNLOADS_DIR,
]
MODEL_SEARCH_PATHS = [os.path.join(d, n) for n in MODEL_CANDIDATES for d in MODEL_SEARCH_DIRS]

SERVER_PORT = 8080
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}/v1/chat/completions"  # v9: model-agnostic API

SYSTEM_PROMPT = """You are "kelpwave-companion", a fully autonomous, highly intelligent AI Agent.
Your goal is to converse with the user and help them with tasks in their Termux environment.

If the user asks you to DO something, you can use the following tools:
1. run_bash: Execute a terminal command. Input is the shell command.
2. read_file: Read a local file. Input is the file path.
3. write_file: Write a local file. Input is JSON: {"path": "...", "content": "..."}
4. web_search: Search the web. Input is a PLAIN TEXT search query (a few keywords, no quotes, no JSON).
5. fetch_page: Read the text content of a web page. Input is the absolute URL.
6. download_file: Download a file from a direct URL and save it to Downloads. Input is the absolute URL.

To use a tool, you MUST respond in this exact format:
THOUGHT: I need to list the files in the directory.
ACTION: run_bash
ACTION_INPUT: ls -la

Then wait for the observation (OBSERVATION: ...) before continuing.

YOUR ENVIRONMENT (already set up, do NOT re-install anything):
- You run inside Termux on the user's Android phone.
- Termux home: /data/data/com.termux/files/home (= ~). NOT visible in the phone's file manager.
- SHARED storage the user CAN see in their file manager: /sdcard/Download/kelpwave
  (your downloads folder; write user-facing files THERE).
- Storage access is ALREADY granted. NEVER run termux-setup-storage.
- Required packages are ALREADY installed. NEVER run pkg install / apt install /
  pkg upgrade - they are slow, flood the output and will time you out.
- python3, git, curl, wget are available in run_bash.

IMPORTANT RULES FOR WEB TOOLS:
- To find something, FIRST use web_search with simple keywords, THEN use the URLs from the results.
- web_search input example: ACTION_INPUT: llama.cpp readme github
- To download a file from GitHub, use the raw URL format:
  https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>
  Example: https://raw.githubusercontent.com/ggml-org/llama.cpp/master/README.md
- NEVER invent or guess URLs - invented URLs always fail with 404. Use ONLY the exact
  URLs that appear in web_search results or that the user gave you.
- Use download_file (not fetch_page) when the user wants to SAVE a file.
- download_file only works with DIRECT file links (ending in .txt/.zip/.pdf/.md etc).
  A page describing or generating files is NOT a file. Good sources of real files:
  raw.githubusercontent.com, or links that end with a file extension.
- To ask the user something, just reply in plain text WITHOUT any ACTION.
  NEVER use run_bash echo to "ask" - the user cannot answer a bash command.
- If the user's request is vague (like "download some file"), don't ask - just pick
  something reasonable yourself: search, take a real URL from results, download it.

Once you have the result, or if you just want to talk to the user, respond directly without ACTION or ACTION_INPUT. Just talk naturally.
"""

def find_model():
    for p in MODEL_SEARCH_PATHS:
        if os.path.exists(p):
            return p
    return None

def is_server_running():
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{SERVER_PORT}/health")
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False

def tail_server_log(n=15):
    try:
        with open(SERVER_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except Exception:
        return "(лог недоступен)"

def start_background_server(model_path):
    print(f"[*] Загружаю модель в RAM: {model_path}")
    if "/storage/shared/" in model_path or "/sdcard/" in model_path:
        print(f"{C_YELLOW}[!] Модель на /sdcard — загрузка через FUSE медленная (1-3 мин).")
        print(f"    Совет: перенеси её командой:")
        print(f"    mkdir -p ~/llama.cpp/models && mv \"{model_path}\" ~/llama.cpp/models/")
        print(f"    — тогда загрузка и работа станут заметно быстрее.{C_END}")

    cmd = [
        LLAMA_SERVER_PATH,
        "-m", model_path,
        "-c", "4096",
        "-t", "5",
        "-tb", "6",
        "-fa", "auto",          # FIX: новый llama.cpp требует значение для -fa
        "--jinja",              # v9: родной chat-шаблон модели (Qwen/Gemma/Llama...)
        "--port", str(SERVER_PORT),
        "--host", "127.0.0.1",
        # --mlock убран: на /sdcard он не работает и ломал запуск
    ]
    try:
        log_f = open(SERVER_LOG_PATH, "w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd,
            stdout=log_f,
            stderr=subprocess.STDOUT,   # FIX: всё пишем в лог, а не в DEVNULL
            stdin=subprocess.DEVNULL,
            preexec_fn=os.setsid
        )
        # FIX: ждём до 180 секунд (7B с /sdcard грузится долго)
        for i in range(180):
            if proc.poll() is not None:
                # Сервер умер — показываем ПОЧЕМУ
                print(f"\n{C_RED}[-] Сервер упал при старте (код {proc.returncode}).")
                print(f"Последние строки server_log.txt:{C_END}")
                print(tail_server_log())
                return None
            if is_server_running():
                print(f"\n{C_GREEN}[+] Сервер загружен и готов к работе! ({i} сек){C_END}")
                return proc
            if i % 10 == 0:
                print(f"    ... загрузка модели, прошло {i} сек (это нормально для 7B)")
            time.sleep(1)
        print(f"{C_RED}[-] Сервер не поднялся за 180 сек. Смотри лог: {SERVER_LOG_PATH}{C_END}")
        print(tail_server_log())
        return proc
    except Exception as e:
        print(f"{C_RED}[-] Не удалось запустить сервер: {e}{C_END}")
        return None

def query_local_server(prompt_history, max_tokens=400, temp=0.3):
    # v9: chat completions API — llama-server сам применяет родной шаблон модели
    # (ChatML для Qwen, свой для Gemma/Llama и т.д.). Код стал моделенезависимым.
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += prompt_history[-10:]

    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temp,
    }
    try:
        req = urllib.request.Request(
            SERVER_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=180) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            res_text = res_data["choices"][0]["message"]["content"].strip()
            res_text = res_text.replace("[end of text]", "").strip()
            # Срезаем "размышления" reasoning-моделей, если просочились
            res_text = re.sub(r'<think>.*?</think>', '', res_text, flags=re.DOTALL).strip()
            if not res_text.startswith("THOUGHT:"):
                res_text = "THOUGHT: " + res_text
            return res_text
    except Exception as e:
        return f"THOUGHT: Error querying local server: {e}. ACTION: none."

def tool_run_bash(command):
    clean_command = command.replace("[end of text]", "").strip()
    # v9: бан тяжёлых команд — окружение уже настроено через tools/setup.sh.
    # pkg install душит CPU (модель ловит таймаут) и заливает контекст выводом.
    BANNED = ["pkg install", "apt install", "pkg upgrade", "apt upgrade",
              "apt-get install", "termux-setup-storage", "pkg update", "apt update"]
    for b in BANNED:
        if b in clean_command:
            return (f"[BLOCKED: '{b}' is not allowed. The environment is ALREADY fully "
                    f"set up (storage access, python3, git, curl, wget). Just use the "
                    f"tools directly. If something is truly missing, tell the user to "
                    f"run tools/setup.sh manually.]")
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    try:
        res = subprocess.run(clean_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60, env=env)
        out = (res.stdout + res.stderr).strip() or "[Success - No Output]"
        # v9: защита контекста модели от огромных выводов
        if len(out) > 1500:
            out = out[:1500] + f"\n... [output truncated, {len(out)} chars total]"
        return out
    except subprocess.TimeoutExpired:
        return "[Error: Command timed out after 60s. Use simpler/faster commands.]"
    except Exception as e:
        return f"[Error: {e}]"

def tool_write_file(input_str):
    try:
        start, end = input_str.find('{'), input_str.rfind('}')
        data = json.loads(input_str[start:end+1])
        path = os.path.join(DOWNLOADS_DIR, data["path"].replace("[end of text]", "").strip().strip("'\""))
        with open(path, "w", encoding="utf-8") as f: f.write(data["content"])
        return f"[Success - Written to {path}]"
    except Exception as e:
        return f"[Error writing file: {e}]"

# ---------- Веб-инструменты (v3: полностью переписаны) ----------
WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"

def http_get(url, data=None, timeout=20):
    """GET/POST с поддержкой gzip и нормальными заголовками браузера."""
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": WEB_UA,
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US,en;q=0.8",
        "Accept-Encoding": "gzip",
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

def _decode_bing_url(u):
    """Bing заворачивает ссылки в редирект /ck/a?...&u=a1<base64>."""
    u = html_mod.unescape(u)
    m = re.search(r'[?&]u=a1([^&]+)', u)
    if not m:
        return u
    b64 = m.group(1)
    b64 += "=" * (-len(b64) % 4)
    try:
        return base64.urlsafe_b64decode(b64).decode("utf-8", errors="replace")
    except Exception:
        return u

def _search_ddg_lite(query, n=4):
    """DuckDuckGo Lite через POST — работает там, где html.duckduckgo.com отдаёт капчу."""
    data = urllib.parse.urlencode({"q": query}).encode()
    page = http_get("https://lite.duckduckgo.com/lite/", data=data).decode("utf-8", errors="replace")
    if "confirm this search was made by a human" in page:
        return []  # капча — переключаемся на запасной движок
    links = re.findall(r'<a rel="nofollow" href="([^"]+)"[^>]*>(.*?)</a>', page)
    snippets = re.findall(r"class=['\"]result-snippet['\"][^>]*>(.*?)</td>", page, re.DOTALL)
    results = []
    for i, (u, t) in enumerate(links[:n]):
        snip = " ".join(strip_tags(snippets[i]).split()) if i < len(snippets) else ""
        results.append(f"Title: {strip_tags(t)}\nSnippet: {snip}\nURL: {html_mod.unescape(u)}\n")
    return results

def _search_bing(query, n=4):
    """Запасной движок: Bing (требует gzip, ссылки декодируются из base64-редиректа)."""
    url = "https://www.bing.com/search?q=" + urllib.parse.quote_plus(query)
    page = http_get(url).decode("utf-8", errors="replace")
    blocks = re.findall(r'<li class="b_algo".*?</li>', page, re.DOTALL)
    results = []
    for b in blocks[:n]:
        m = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', b, re.DOTALL)
        if not m:
            continue
        link = _decode_bing_url(m.group(1))
        title = strip_tags(m.group(2))
        sm = re.search(r'<p class="b_lineclamp[^"]*"[^>]*>(.*?)</p>', b, re.DOTALL)
        snippet = " ".join(strip_tags(sm.group(1)).split()) if sm else ""
        results.append(f"Title: {title}\nSnippet: {snippet}\nURL: {link}\n")
    return results

def tool_web_search(query):
    clean_query = clean_tool_input(query)
    errors = []
    for engine_name, engine_fn in [("DuckDuckGo", _search_ddg_lite), ("Bing", _search_bing)]:
        try:
            results = engine_fn(clean_query)
            if results:
                return f"[Search engine: {engine_name}]\n" + "\n".join(results)
            errors.append(f"{engine_name}: no results/captcha")
        except Exception as e:
            errors.append(f"{engine_name}: {e}")
    return "[No search results found. Engines tried: " + "; ".join(errors) + "]"

def tool_fetch_page(url):
    clean_url = clean_tool_input(url)
    if not clean_url.startswith("http"):
        return "[Error: fetch_page input must be an absolute URL starting with http(s)://]"
    try:
        raw = http_get(clean_url)
        text = raw.decode("utf-8", errors="replace")
        # Если это не HTML (например, .md или .txt с raw.githubusercontent) — отдаём как есть
        if "<html" not in text[:2000].lower() and "<body" not in text[:2000].lower():
            return text[:3000] + ("\n... [truncated]" if len(text) > 3000 else "")

        # v8: СНАЧАЛА собираем все ссылки (раньше они вырезались вместе с тегами!)
        base = clean_url
        links = []
        seen = set()
        for m in re.finditer(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', text, re.DOTALL | re.IGNORECASE):
            href = html_mod.unescape(m.group(1).strip())
            label = " ".join(strip_tags(m.group(2)).split())[:60]
            absolute = urllib.parse.urljoin(base, href)
            if not absolute.startswith("http") or absolute in seen:
                continue
            seen.add(absolute)
            links.append((absolute, label))

        # Прямые ссылки на файлы — в начало списка (их обычно и ищет агент)
        FILE_EXT = re.compile(r'\.(txt|zip|pdf|json|csv|md|xml|gguf|tar|gz|7z|docx|xlsx|png|jpg|mp3|wav)([?#]|$)', re.IGNORECASE)
        file_links = [(u, l) for u, l in links if FILE_EXT.search(u)]
        page_links = [(u, l) for u, l in links if not FILE_EXT.search(u)]

        body = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r'<style.*?>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r'<[^>]+>', ' ', body)
        body = " ".join(html_mod.unescape(body).split())

        out = body[:1800] + ("\n... [text truncated]" if len(body) > 1800 else "")
        if file_links:
            out += "\n\n=== DIRECT FILE LINKS ON THIS PAGE (use these with download_file!) ===\n"
            out += "\n".join(f"- {u}  ({l})" for u, l in file_links[:15])
        if page_links:
            out += "\n\n=== OTHER LINKS ON THIS PAGE ===\n"
            out += "\n".join(f"- {u}  ({l})" for u, l in page_links[:10])
        return out
    except Exception as e:
        return f"[Error fetching page: {e}]"

def tool_download_file(url):
    """Скачивает файл по прямой ссылке в Download/kelpwave/."""
    clean_url = clean_tool_input(url)
    if not clean_url.startswith("http"):
        return "[Error: download_file input must be an absolute URL starting with http(s)://]"
    # GitHub: автоматически превращаем ссылку на blob в raw
    m = re.match(r'https://github\.com/([^/]+)/([^/]+)/blob/(.+)', clean_url)
    if m:
        clean_url = f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}"
    try:
        raw = http_get(clean_url, timeout=60)
        # v6: проверка "это файл или веб-страница?"
        head = raw[:2000].decode("utf-8", errors="replace").lower()
        if "<!doctype html" in head or "<html" in head:
            return ("[Error: this URL is an HTML PAGE, not a downloadable file. "
                    "Downloading it would just save the page itself. "
                    "Look for a DIRECT file link (usually ends with .txt/.zip/.pdf/.json etc). "
                    "Tip: pages with 'generator' in the name are tools, not files.]")
        fname = os.path.basename(urllib.parse.urlparse(clean_url).path) or "downloaded_file"
        fname = re.sub(r'[^\w.\-]', '_', fname)
        dest = os.path.join(DOWNLOADS_DIR, fname)
        with open(dest, "wb") as f:
            f.write(raw)
        preview = raw[:300].decode("utf-8", errors="replace")
        return f"[Success - Downloaded {len(raw)} bytes to {dest}]\nPreview:\n{preview}"
    except Exception as e:
        return f"[Error downloading file: {e}]"

def parse_action(output):
    output = output.replace("[end of text]", "").strip()
    thought_match = re.search(r"THOUGHT:\s*(.*?)(?=\nACTION:|\Z)", output, re.DOTALL | re.IGNORECASE)
    action_match = re.search(r"ACTION:\s*(\w+)", output, re.IGNORECASE)
    action_input_match = re.search(r"ACTION_INPUT:\s*(.*)", output, re.DOTALL | re.IGNORECASE)
    t = thought_match.group(1).strip() if thought_match else ""
    a = action_match.group(1).strip() if action_match else ""
    ai = action_input_match.group(1).strip() if action_input_match else ""
    return t, a, ai

# ---------- URL Guard (v5) ----------
URL_RE = re.compile(r'https?://[^\s"\'<>\)\]]+')

def extract_urls(text):
    """Достаёт все URL из текста (результаты поиска, сообщения пользователя)."""
    return set(u.rstrip('.,;:!?') for u in URL_RE.findall(text or ""))

def is_known_url(url, known_urls):
    """URL разрешён, если он встречался дословно, или является вариантом
    известного (github blob->raw), или это страница с известного домена+пути."""
    if url in known_urls:
        return True
    # github.com/owner/repo/blob/... преобразуется в raw — разрешаем обе формы
    m = re.match(r'https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/(.+)', url)
    if m:
        blob_form = f"https://github.com/{m.group(1)}/{m.group(2)}/blob/{m.group(3)}"
        if blob_form in known_urls:
            return True
    return False

def url_exists(url, timeout=8):
    """v7: быстрая проверка, существует ли URL на самом деле (HEAD-запрос).
    Так выдуманные, но УГАДАННЫЕ моделью ссылки не блокируются зря."""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": WEB_UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except urllib.error.HTTPError as e:
        # 405 = HEAD не поддерживается, но URL живой
        return e.code in (403, 405)
    except Exception:
        return False

def stop_server(server_process):
    if server_process:
        try:
            os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
        except Exception:
            pass

def main():
    print(f"{C_BLUE}🌊 KELPWAVE - ULTIMATE INTERACTIVE AGENT COMPANION v9 (MODEL-AGNOSTIC){C_END}")

    # --- Предполётные проверки (FIX: раньше их не было) ---
    if not os.path.exists(LLAMA_SERVER_PATH):
        print(f"{C_RED}[-] Не найден llama-server: {LLAMA_SERVER_PATH}")
        print(f"    Проверь сборку: ls ~/llama.cpp/build/bin/ | grep server{C_END}")
        sys.exit(1)

    model_path = find_model()
    if not model_path:
        print(f"{C_RED}[-] Модель {MODEL_NAME} не найдена. Искал тут:")
        for p in MODEL_SEARCH_PATHS:
            print(f"    - {p}")
        print(f"{C_END}")
        sys.exit(1)

    size_gb = os.path.getsize(model_path) / 1024**3
    print(f"[*] Модель: {model_path} ({size_gb:.2f} ГБ)")
    if size_gb < 3.5:
        print(f"{C_YELLOW}[!] Файл подозрительно маленький для 7B Q4_K_M (~4.7 ГБ) — возможно, скачан не полностью!{C_END}")

    server_process = None
    if not is_server_running():
        server_process = start_background_server(model_path)
        if server_process is None:
            print(f"{C_RED}[-] Запуск не удался. Пришли содержимое {SERVER_LOG_PATH} агенту-помощнику!{C_END}")
            sys.exit(1)
    else:
        print(f"{C_GREEN}[+] Подключился к уже запущенному серверу.{C_END}")

    print("\n[*] Агент слушает. Попроси его поговорить, поискать в сети или выполнить задачу!")
    print("[*] Напиши 'exit' для выхода.\n" + "="*60)

    history = []

    while True:
        try:
            user_input = input(f"\n{C_BOLD}👤 You:{C_END} ").strip()
            if not user_input: continue
            if user_input.lower() == 'exit':
                print("[*] Останавливаю сервер и освобождаю RAM...")
                stop_server(server_process)
                print("Goodbye, friend! Keep coding! 🌊")
                break

            history.append({"role": "user", "content": user_input})

            agent_turn_completed = False
            loop_steps = 0
            max_steps = 6
            seen_calls = set()      # (action, input) — что уже вызывалось в этом ходу
            repeat_strikes = 0      # сколько раз агент пытался повторить то же самое
            known_urls = extract_urls(user_input)  # v5: URL, которым можно доверять

            while not agent_turn_completed and loop_steps < max_steps:
                response = query_local_server(history)
                thought, action, action_input = parse_action(response)

                action = action.strip()
                action_input = action_input.replace("[end of text]", "").strip()

                if action and action.lower() in ["run_bash", "write_file", "read_file", "web_search", "fetch_page", "download_file"]:
                    call_signature = (action.lower(), action_input.lower())

                    # --- АНТИ-ЗАЦИКЛИВАНИЕ (v4) ---
                    if call_signature in seen_calls:
                        repeat_strikes += 1
                        print(f"\n{C_YELLOW}[⚠️ LOOP GUARD] Агент повторяет тот же вызов ({action}). Перенаправляю...{C_END}")
                        if repeat_strikes >= 2:
                            # Дважды настаивает на повторе — принудительно требуем финальный ответ
                            history.append({"role": "assistant", "content": response})
                            history.append({"role": "user", "content":
                                "OBSERVATION:\n[SYSTEM] You are stuck in a loop. STOP using tools NOW. "
                                "Look at the observations you ALREADY received above and give the user "
                                "your final answer in plain text, without ACTION."})
                            response = query_local_server(history)
                            clean_reply = response.replace("THOUGHT:", "").strip()
                            if "ACTION:" in clean_reply:
                                clean_reply = clean_reply.split("ACTION:")[0].strip()
                            print(f"\n🌊 {C_BOLD}{C_BLUE}kelpwave:{C_END} {clean_reply}")
                            history.append({"role": "assistant", "content": response})
                            agent_turn_completed = True
                            break
                        # Первый повтор: не выполняем инструмент, а подсказываем следующий шаг
                        history.append({"role": "assistant", "content": response})
                        history.append({"role": "user", "content":
                            "OBSERVATION:\n[SYSTEM] You ALREADY ran this exact tool call and have its result above. "
                            "Do NOT repeat it. Take the NEXT step: e.g. pick a URL from the search results and use "
                            "fetch_page or download_file with it, or answer the user directly."})
                        loop_steps += 1
                        continue
                    seen_calls.add(call_signature)

                    # --- URL GUARD (v5, поумнел в v7) ---
                    if action.lower() in ("download_file", "fetch_page"):
                        candidate = clean_tool_input(action_input)
                        if candidate.startswith("http") and not is_known_url(candidate, known_urls):
                            # v7: не блокируем вслепую — проверяем реальным запросом
                            print(f"\n{C_YELLOW}[🛡️ URL GUARD] URL не из наблюдений: {candidate[:70]} — проверяю...{C_END}")
                            if url_exists(candidate):
                                print(f"{C_GREEN}[🛡️ URL GUARD] URL существует — разрешаю.{C_END}")
                                known_urls.add(candidate)
                            else:
                                print(f"{C_RED}[🛡️ URL GUARD] URL не существует — блокирую.{C_END}")
                                real_urls = "\n".join(f"- {u}" for u in sorted(known_urls)[:8]) or "(none yet — use web_search first)"
                                history.append({"role": "assistant", "content": response})
                                history.append({"role": "user", "content":
                                    f"OBSERVATION:\n[SYSTEM] BLOCKED: I checked this URL and it does NOT exist "
                                    f"(you invented it). NEVER invent URLs. You may ONLY use URLs that "
                                    f"appeared in earlier observations. Currently known REAL urls:\n{real_urls}\n"
                                    f"Pick one of these, or use web_search to find more."})
                                loop_steps += 1
                                continue

                    print(f"\n🧠 {C_CYAN}Agent Thought:{C_END} {thought}")
                    print(f"🎬 {C_CYAN}Calling Tool {action} with:{C_END} {action_input}")

                    if action.lower() == "run_bash":
                        obs = tool_run_bash(action_input)
                    elif action.lower() == "write_file":
                        obs = tool_write_file(action_input)
                    elif action.lower() == "read_file":
                        path = os.path.join(DOWNLOADS_DIR, action_input.strip().strip("'\""))
                        try:
                            with open(path, "r", encoding="utf-8") as f: obs = f.read()
                        except Exception as e: obs = f"[Error: {e}]"
                    elif action.lower() == "web_search":
                        obs = tool_web_search(action_input)
                        # v4: подталкиваем модель к следующему шагу
                        obs += "\n[SYSTEM] Next step: pick ONE relevant URL above and use fetch_page or download_file with it. Do not search again unless these results are useless."
                    elif action.lower() == "fetch_page":
                        obs = tool_fetch_page(action_input)
                    elif action.lower() == "download_file":
                        obs = tool_download_file(action_input)
                    else:
                        obs = "[Error: Unknown tool]"

                    print(f"👀 {C_GREEN}Observation Result:{C_END}\n{obs[:500]}")

                    known_urls |= extract_urls(obs)  # v5: запоминаем реальные URL из результатов

                    history.append({"role": "assistant", "content": response})
                    history.append({"role": "user", "content": f"OBSERVATION:\n{obs}"})
                    loop_steps += 1
                else:
                    clean_reply = response.replace("THOUGHT:", "").strip()
                    if "ACTION:" in clean_reply:
                        clean_reply = clean_reply.split("ACTION:")[0].strip()
                    print(f"\n🌊 {C_BOLD}{C_BLUE}kelpwave:{C_END} {clean_reply}")
                    history.append({"role": "assistant", "content": response})
                    agent_turn_completed = True

            # v4: лимит шагов исчерпан — раньше тут было молчание, теперь требуем итог
            if not agent_turn_completed:
                print(f"\n{C_YELLOW}[⚠️ STEP LIMIT] Лимит шагов исчерпан, запрашиваю финальный ответ...{C_END}")
                history.append({"role": "user", "content":
                    "OBSERVATION:\n[SYSTEM] Tool budget exhausted. Summarize what you found/did above and "
                    "give the user a final answer in plain text. Do NOT use any ACTION."})
                response = query_local_server(history)
                clean_reply = response.replace("THOUGHT:", "").strip()
                if "ACTION:" in clean_reply:
                    clean_reply = clean_reply.split("ACTION:")[0].strip()
                print(f"\n🌊 {C_BOLD}{C_BLUE}kelpwave:{C_END} {clean_reply}")
                history.append({"role": "assistant", "content": response})

        except KeyboardInterrupt:
            stop_server(server_process)
            break

if __name__ == "__main__":
    main()
