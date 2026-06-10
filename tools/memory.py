#!/usr/bin/env python3
"""
🌊 KELPWAVE MEMORY SYSTEM v1
Простая долгосрочная память агента.
Хранит "уроки", которые агент извлекает из неудач и сомнительных результатов.

Файл: ~/storage/shared/Download/kelpwave/agent_lessons.json
"""

import os
import json
from datetime import datetime

DOWNLOADS_DIR = "/data/data/com.termux/files/home/storage/shared/Download/kelpwave"
MEMORY_FILE = os.path.join(DOWNLOADS_DIR, "agent_lessons.json")
MAX_LESSONS = 50  # чтобы не раздувать промпт


def load_lessons():
    """Загружает все уроки"""
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("lessons", [])
    except Exception:
        return []


def save_lessons(lessons):
    """Сохраняет уроки (с ограничением по количеству)"""
    lessons = lessons[-MAX_LESSONS:]  # оставляем только последние
    data = {
        "lessons": lessons,
        "last_updated": datetime.now().isoformat()
    }
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_lesson(lesson_text, context=""):
    """Добавляет новый урок"""
    if not lesson_text or len(lesson_text) < 10:
        return

    lessons = load_lessons()

    # Простая защита от дубликатов
    lesson_text = lesson_text.strip()
    if any(lesson_text in l for l in lessons):
        return

    entry = {
        "lesson": lesson_text,
        "context": context[:200] if context else "",
        "timestamp": datetime.now().isoformat()
    }
    lessons.append(entry)
    save_lessons(lessons)
    print(f"\033[95m[🧠 MEMORY] Новый урок сохранён: {lesson_text[:80]}...\033[0m")


def get_lessons_context(max_lessons=8):
    """Возвращает уроки в виде текста для промпта"""
    lessons = load_lessons()
    if not lessons:
        return ""

    recent = lessons[-max_lessons:]
    text = "\n\n=== LESSONS LEARNED FROM PAST EXPERIENCE ===\n"
    for i, entry in enumerate(recent, 1):
        text += f"{i}. {entry['lesson']}\n"
    text += "=== END OF LESSONS ===\n\n"
    return text


def clear_lessons():
    """Полностью очищает память (для тестов)"""
    if os.path.exists(MEMORY_FILE):
        os.remove(MEMORY_FILE)
    print("[MEMORY] Память очищена.")