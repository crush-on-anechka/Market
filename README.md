## Описание проекта MARKET

MARKET - Python скрипт, автоматизирующий торговлю на фондовой бирже в приложении Tinkoff Invest. Скрипт парсит сайт investing.com, где собирает текущие котировки, реализует логику отслеживания и на основе выставленных вводных данных совершает покупку/продажу акций в приложении Tinkoff, а также информирует о действиях через Telegram.


#### Технологии, используемые в проекте
* Python 3.7  
* Python-telegram-bot  
* Tinkoff-investments  

#### Шаблон наполнения env-файла
TELEGRAM_TOKEN=your_token  
TELEGRAM_CHAT_ID=your_chat_id  
TINKOFF_ID=your_id  

#### Запуск приложения
- Установите и запустите виртуальное окружение
```
python3 -m venv venv
``` 
- Установите зависимости
```
pip install -r requirements.txt
``` 
- Скрипт готов к работе!

#### Разработчики
[Саша Смирнов](https://github.com/crush-on-anechka)
