OMNIRO ONLANE - юридическая база

ФАЙЛЫ
main.py, laws.json, icon.png, icon.ico, requirements.txt - загружаются в корень репозитория GitHub.
build.yml - создаётся на GitHub по пути .github/workflows/build.yml (папки с телефона не грузятся).

ОБНОВИТЬ ПРОГРАММУ
1. GitHub -> твой репозиторий -> Add file -> Upload files.
2. Выбери нужные файлы (с теми же именами) и нажми Commit changes. Они заменят старые.
3. Вкладка Actions -> дождись зелёной галочки -> открой запуск -> Artifacts -> OMNIRO-ONLANE.
4. Распакуй zip на ПК, внутри OMNIRO ONLANE.exe.

ОБНОВЛЕНИЕ ЗАКОНОВ ДЛЯ ИГРОКОВ
Правь laws.json, увеличивай "version". Выложи файл на хостинг, ссылку впиши в main.py в строку UPDATE_URL = "".
