#!/usr/bin/env python3
# 🩺 KELPWAVE DOCTOR — проверка окружения перед запуском агентов
# Запуск: python ~/kelpwave/tools/doctor.py
# Проверяет всё, что нужно агентам, и для каждой проблемы даёт готовую команду.

import os, sys, shutil, subprocess

G, R, Y, B, E = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

HOME = "/data/data/com.termux/files/home"
DOWNLOADS_DIR = os.path.join(HOME, "storage/shared/Download/kelpwave")
LLAMA_BIN_DIR = os.path.join(HOME, "llama.cpp/build/bin")

MODELS = {
    "companion (7B)": [
        os.path.join(HOME, "llama.cpp/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"),
        os.path.join(DOWNLOADS_DIR, "qwen2.5-coder-7b-instruct-q4_k_m.gguf"),
    ],
    "reflexion (0.5B)": [
        os.path.join(HOME, "llama.cpp/models/qwen2.5-0.5b-instruct-q4_k_m.gguf"),
        os.path.join(DOWNLOADS_DIR, "qwen2.5-0.5b-instruct-q4_k_m.gguf"),
    ],
}

MODEL_URLS = {
    "companion (7B)": "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
    "reflexion (0.5B)": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
}

issues = 0

def ok(msg):
    print(f"  {G}[OK]{E} {msg}")

def fail(msg, fix=None):
    global issues
    issues += 1
    print(f"  {R}[!!]{E} {msg}")
    if fix:
        print(f"       {Y}Починить:{E} {fix}")

def warn(msg, fix=None):
    print(f"  {Y}[..]{E} {msg}")
    if fix:
        print(f"       {Y}Совет:{E} {fix}")

print(f"{B}🩺 KELPWAVE DOCTOR — проверка окружения{E}\n")

# 1. Python
print(f"{B}1. Python{E}")
v = sys.version_info
if v >= (3, 8):
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
else:
    fail(f"Python {v.major}.{v.minor} слишком старый", "pkg install -y python")

# 2. Доступ к общему хранилищу
print(f"{B}2. Хранилище{E}")
shared = os.path.join(HOME, "storage/shared")
if os.path.isdir(shared):
    ok("Доступ к /sdcard настроен")
else:
    fail("Нет доступа к общему хранилищу", "termux-setup-storage  (и разреши доступ в диалоге)")

if os.path.isdir(DOWNLOADS_DIR):
    ok(f"Рабочая папка есть: {DOWNLOADS_DIR}")
else:
    fail("Нет рабочей папки агентов", f"mkdir -p {DOWNLOADS_DIR}")

# 3. llama.cpp
print(f"{B}3. llama.cpp{E}")
server = os.path.join(LLAMA_BIN_DIR, "llama-server")
completion = os.path.join(LLAMA_BIN_DIR, "llama-completion")
if os.path.exists(server):
    ok("llama-server найден (нужен для companion)")
else:
    fail("llama-server не найден",
         "cd ~/llama.cpp && cmake -B build && cmake --build build --config Release -j4")
if os.path.exists(completion):
    ok("llama-completion найден (нужен для reflexion)")
else:
    warn("llama-completion не найден (reflexion работать не будет)",
         "проверь сборку: ls ~/llama.cpp/build/bin/")

# 4. Модели
print(f"{B}4. Модели{E}")
for name, paths in MODELS.items():
    found = None
    for p in paths:
        if os.path.exists(p):
            found = p
            break
    if found:
        size_gb = os.path.getsize(found) / 1024**3
        ok(f"{name}: {found} ({size_gb:.2f} ГБ)")
        if "/storage/shared/" in found:
            warn(f"{name} лежит на /sdcard — грузится медленно",
                 f'mkdir -p ~/llama.cpp/models && mv "{found}" ~/llama.cpp/models/')
        expected = 4.0 if "7b" in found.lower() else 0.3
        if size_gb < expected:
            fail(f"{name}: файл подозрительно маленький — возможно, скачан не полностью",
                 f"скачай заново: wget -c -P ~/llama.cpp/models/ \"{MODEL_URLS[name]}\"")
    else:
        fail(f"{name}: модель не найдена",
             f"wget -c -P ~/llama.cpp/models/ \"{MODEL_URLS[name]}\"")

# 5. Свободное место и RAM
print(f"{B}5. Ресурсы{E}")
try:
    st = os.statvfs(HOME)
    free_gb = st.f_bavail * st.f_frsize / 1024**3
    if free_gb > 6:
        ok(f"Свободно в домашней папке: {free_gb:.1f} ГБ")
    else:
        warn(f"Мало места: {free_gb:.1f} ГБ (для 7B-модели нужно ~5 ГБ + запас)")
except Exception:
    warn("Не удалось проверить свободное место")

try:
    with open("/proc/meminfo") as f:
        mem = dict(line.split(":") for line in f if ":" in line)
    total_gb = int(mem["MemTotal"].strip().split()[0]) / 1024**2
    avail_gb = int(mem["MemAvailable"].strip().split()[0]) / 1024**2
    if avail_gb > 5.5:
        ok(f"RAM: всего {total_gb:.0f} ГБ, доступно {avail_gb:.1f} ГБ")
    else:
        warn(f"Доступно только {avail_gb:.1f} ГБ RAM — 7B может не влезть",
             "закрой другие приложения перед запуском companion")
except Exception:
    warn("Не удалось проверить RAM")

# 6. Интернет
print(f"{B}6. Интернет{E}")
try:
    import urllib.request
    urllib.request.urlopen("https://lite.duckduckgo.com", timeout=5)
    ok("Сеть доступна, поисковик отвечает")
except Exception as e:
    warn(f"Проблема с сетью: {e}", "web_search у companion может не работать")

# Итог
print()
if issues == 0:
    print(f"{G}{B}✅ Всё готово! Запускай: python ~/kelpwave/agents/kelpwave_companion.py{E}")
else:
    print(f"{R}{B}Найдено проблем: {issues}. Выполни команды из строк «Починить» выше.{E}")
sys.exit(1 if issues else 0)
