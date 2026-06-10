# 🌊 Kelpwave

Локальные ИИ-агенты для Android (Termux + llama.cpp). Работают полностью офлайн на телефоне,
без облачных API.

## Состав

| Файл | Что это |
|---|---|
| `agents/kelpwave_companion.py` | Интерактивный чат-агент с инструментами: bash, файлы, веб-поиск, скачивание. Модель: Qwen2.5-Coder-7B (через llama-server) |
| `agents/kelpwave_reflexion.py` | Самообучающийся кодер: пишет solution.py, тестирует, учится на ошибках (архитектура Reflexion). Модель: Qwen2.5-0.5B |

## Требования

- Android-телефон (рекомендуется 12+ ГБ RAM для 7B-модели)
- [Termux](https://f-droid.org/packages/com.termux/) (из F-Droid)
- Собранный [llama.cpp](https://github.com/ggml-org/llama.cpp) в `~/llama.cpp/build/bin/`
- Модели GGUF:
  - `qwen2.5-coder-7b-instruct-q4_k_m.gguf` (~4.4 ГБ) — для companion
  - `qwen2.5-0.5b-instruct-q4_k_m.gguf` (~0.4 ГБ) — для reflexion

Модели НЕ хранятся в этом репозитории (слишком большие). Скачать можно с
[HuggingFace](https://huggingface.co/Qwen). Положи их в `~/llama.cpp/models/`
или в `~/storage/shared/Download/kelpwave/` — агент найдёт сам.

## Быстрый старт

```bash
pkg install -y python git
termux-setup-storage
git clone https://github.com/<ТВОЙ_ЛОГИН>/kelpwave.git ~/kelpwave
python ~/kelpwave/agents/kelpwave_companion.py
```

## Структура рабочих файлов (не в git)

Агенты пишут рабочие файлы в `~/storage/shared/Download/kelpwave/`:
- `lessons_learned.json` — память reflexion-агента (уроки из ошибок)
- `server_log.txt` — лог llama-server (смотреть при проблемах с запуском)
- `solution.py`, `successful_solution_*.py` — результаты работы reflexion
- скачанные агентом файлы

## История версий companion

- **v4** — Loop Guard: защита от зацикливания, принудительный финальный ответ
- **v3** — починен веб-поиск (DDG Lite + Bing fallback), gzip в fetch_page, новый инструмент download_file
- **v2** — `-fa auto`, лог сервера в файл, убран `--mlock`, ожидание загрузки 180 с, предполётные проверки
- **v1** — исходная версия (сгенерирована ИИ-агентом)
