# Как залить проект на GitHub из Termux (один раз)

## 1. Создай репозиторий на GitHub

1. Зайди на https://github.com (зарегистрируйся, если нет аккаунта)
2. Нажми **+** → **New repository**
3. Название: `kelpwave`, видимость: **Private** (или Public — тогда я смогу читать его без токена)
4. НЕ добавляй README/gitignore при создании (они у нас уже есть)
5. Нажми **Create repository**

## 2. Сделай токен для доступа из Termux

GitHub не принимает пароль из консоли — нужен токен:

1. GitHub → Settings → Developer settings → **Personal access tokens** → Tokens (classic)
2. **Generate new token (classic)**
3. Галочка: **repo** (полный доступ к репозиториям)
4. Скопируй токен (показывается один раз!) — например в заметки

## 3. Залей проект (команды для Termux)

```bash
pkg install -y git
cd ~/kelpwave   # папка с файлами проекта

git init
git add .
git commit -m "Initial commit: kelpwave agents v4"
git branch -M main
git remote add origin https://github.com/<ЛОГИН>/kelpwave.git
git push -u origin main
```

При push спросит логин и пароль:
- Username: твой логин GitHub
- Password: **вставь токен** (не пароль аккаунта!)

Чтобы не вводить каждый раз:
```bash
git config --global credential.helper store
```
(после первого успешного push токен запомнится)

## 4. Повседневная работа

После любых изменений:
```bash
cd ~/kelpwave
git add .
git commit -m "что поменял"
git push
```

Получить свежую версию (например, после моих правок):
```bash
cd ~/kelpwave
git pull
```

## 5. Как делиться проектом с ИИ-агентом

- **Public репозиторий:** просто кидай агенту ссылку
  `https://github.com/<ЛОГИН>/kelpwave` — он скачает сам.
- **Private:** агент не сможет его прочитать. Варианты:
  - сделай репозиторий публичным;
  - или скачивай zip: Code → Download ZIP → прикрепляй в чат.
