#!/usr/bin/env python3
"""
🌊 KELPWAVE LAUNCHER v10
Единая точка входа. При первом запуске автоматически:
- настраивает окружение (setup.sh)
- проверяет всё через doctor.py
- запускает companion

Запуск: python ~/kelpwave/run.py
"""

import os
import sys
import subprocess

HOME = "/data/data/com.termux/files/home"
SETUP_SCRIPT = os.path.join(HOME, "kelpwave/tools/setup.sh")
DOCTOR_SCRIPT = os.path.join(HOME, "kelpwave/tools/doctor.py")
COMPANION = os.path.join(HOME, "kelpwave/agents/kelpwave_companion_v11_memory.py")

def run_setup():
    print("\n[*] Запускаю настройку окружения (setup.sh)...")
    try:
        subprocess.run(["bash", SETUP_SCRIPT], check=True)
    except subprocess.CalledProcessError:
        print("[!] Setup завершился с ошибкой. Проверь вывод выше.")
        sys.exit(1)

def run_doctor():
    print("\n[*] Проверяю окружение (doctor.py)...")
    result = subprocess.run([sys.executable, DOCTOR_SCRIPT])
    if result.returncode != 0:
        print("\n[!] Доктор нашёл проблемы. Исправь их и запусти снова.")
        sys.exit(1)

def main():
    print("🌊 KELPWAVE LAUNCHER v10\n")

    # 1. Setup (если ещё не настроено)
    if not os.path.isdir(os.path.join(HOME, "storage/shared")):
        run_setup()
    else:
        print("[OK] Хранилище уже настроено — пропускаю setup")

    # 2. Doctor
    run_doctor()

    # 3. Запуск агента
    print("\n[*] Всё готово! Запускаю kelpwave_companion.py...\n")
    os.execv(sys.executable, [sys.executable, COMPANION])

if __name__ == "__main__":
    main()