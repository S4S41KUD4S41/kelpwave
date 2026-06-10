#!/data/data/com.termux/files/usr/bin/bash
# 🛠️ KELPWAVE SETUP — предустановка окружения (идея владельца, как в AUTOMATIC1111)
# Запуск: bash ~/kelpwave/tools/setup.sh
# Ставит все пакеты ЗАРАНЕЕ, чтобы агенту никогда не приходилось делать
# pkg install во время работы (это душит CPU и роняет модель по таймауту).

set -e
G="\033[92m"; Y="\033[93m"; B="\033[1m"; E="\033[0m"

echo -e "${B}🛠️ KELPWAVE SETUP${E}"

# 1. Доступ к общему хранилищу
if [ ! -d "$HOME/storage/shared" ]; then
    echo -e "${Y}[*] Настраиваю доступ к хранилищу (разреши в диалоге!)...${E}"
    termux-setup-storage
    sleep 3
else
    echo -e "${G}[OK] Доступ к хранилищу уже настроен${E}"
fi

# 2. Базовые пакеты (всё, что может понадобиться агенту)
echo -e "${Y}[*] Обновляю списки пакетов и ставлю базовый набор...${E}"
pkg update -y -o Dpkg::Options::="--force-confold" 2>&1 | tail -1
pkg install -y python git curl wget zip unzip jq file 2>&1 | tail -1
echo -e "${G}[OK] Пакеты: python git curl wget zip unzip jq file${E}"

# 3. Рабочая папка агентов
mkdir -p "$HOME/storage/shared/Download/kelpwave"
echo -e "${G}[OK] Рабочая папка: /sdcard/Download/kelpwave${E}"

# 4. Git-идентичность (если не настроена)
if ! git config --global user.name >/dev/null 2>&1; then
    git config --global user.name "kelpwave-user"
    git config --global user.email "kelpwave-user@localhost"
    echo -e "${G}[OK] Git-идентичность настроена (поменяй при желании)${E}"
else
    echo -e "${G}[OK] Git уже настроен: $(git config --global user.name)${E}"
fi
git config --global credential.helper store

# 5. Финальная проверка окружения доктором
echo
echo -e "${B}[*] Запускаю диагностику...${E}"
python "$(dirname "$0")/doctor.py" || true

echo
echo -e "${G}${B}✅ Setup завершён. Если доктор нашёл проблемы — выполни его советы.${E}"
echo -e "Запуск агента: ${B}python ~/kelpwave/agents/kelpwave_companion.py${E}"
