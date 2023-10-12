# Проект парсинга pep

## Автор
- Анна Котова
- E-mail: kotova.a.a.97@mail.ru
- Telegram: @annkotttt

##  Описание
Парсер собирает данные обо всех PEP документах, сравнивает статусы и записывает их в файл, также реализованы сбор информации о статусе версий, скачивание архива с документацией и сбор ссылок о новостях в Python, логирует свою работу и ошибки в командную строку и файл логов.


## Технологии проекта
BeautifulSoup4 - библиотека для парсинга.
Prettytable - библиотека для отображения табличных данных.
Logging - Логирование работы и отслеживания ошибок


## Как запустить проект:
Клонировать репозиторий и перейти в него в командной строке:
```
git clone git@github.com:AnnaKotovapr/bs4_parser_pep.git
cd bs4_parser_pep
```
Cоздать и активировать виртуальное окружение:
```
python3 -m venv env
source env/bin/activate
```
Установить зависимости из файла requirements.txt:
```
python3 -m pip install --upgrade pip
pip install -r requirements.txt
```

## Примеры команд
Выведет справку по использованию
python main.py pep -h

Создаст csv файл с таблицей из двух колонок: «Статус» и «Количество»:
python main.py pep --output file

Выводит таблицу prettytable с тремя колонками: "Ссылка на документацию", "Версия", "Статус":
python main.py latest-versions -o pretty

Выводит ссылки в консоль на нововведения в python:
python main.py whats-new
