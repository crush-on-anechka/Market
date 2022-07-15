from __future__ import annotations
from dotenv import load_dotenv
import telegram
import requests
import time
import urls
import os

load_dotenv()

TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID')

PARAMS = {'fieldmap': 'indices.minimal'}
URL_static = 'https://api.investing.com/api/financialdata/table/list/'

DATA: list = {}
CONS_DATA: list = []
NAMES_LIST: set = set()
TRADE: dict = {}
GENERAL_PERCENT: float = 0

RETRY_TIME = 60
INTERVAL_MINUTES = 20
GOLDEN_FIGURE = 2.1
TARGET_PERCENT = 1.1


def make_urls_str():
    urls_str = ''
    for id in urls.urls.values():
        urls_str += '%2C' + str(id)
    urls_str = urls_str[3:]
    return urls_str


def send_message(bot, message):
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    print(message)


def buy(name, cur_price, bot):
    """Если названия нет в словаре TRADE - добавляет"""
    if name not in TRADE:
        TRADE[name] = cur_price
        buy_msg = f'{name}: покупка по {cur_price}'
        send_message(bot, buy_msg)


def sell(name, cur_price, bot):
    """Вычисляет разницу между текущей ценой и ценой, зафиксированной
       в словаре TRADE, убирает компанию из TRADE, прибавляет результат
       торговли к глобальном итогу и выводит инфо о сделке и итог в терминал.
    """
    result = - round(
        (TRADE.get(name) - cur_price) / cur_price * 100, 1
        )
    sell_msg = f'{name}: продажа, результат: {result}% '
    f'({TRADE.get(name)} >> {cur_price})'
    send_message(bot, sell_msg)
    global GENERAL_PERCENT
    GENERAL_PERCENT += result
    result_msg = f'''>> Общий результат торговли: {round(GENERAL_PERCENT, 1)}%
>> Открытые позиции: {TRADE}%'''
    send_message(bot, result_msg)
    TRADE.pop(name)


def get_data(CONS_DATA: list[dict], count, bot):
    """Получает данные по каждой итерации из main, по каждой компании
       расчитывает текущую цену и цену на момент времени в прошлом за
       выбранный интервал.
       Если в словаре TRADE (заполняется в функции buy()) есть итерируемая
       компания - идет на sell().
       Если отрицательная разница между котировками превышает золотое
       число (цена падает) - buy() и выводит в терминал разницу котировок.
    """
    for name in NAMES_LIST:
        prev_count = count - INTERVAL_MINUTES
        prev_price = None
        data_list = [data[name] for data in CONS_DATA]
        for data in data_list:
            if data.get(count) is not None:
                cur_price = float(data.get(count))
            if data.get(prev_count) is not None:
                prev_price = float(data.get(prev_count))
        if (TRADE.get(name) is not None
                and abs(TRADE.get(name) - cur_price)
                / cur_price > TARGET_PERCENT / 100):
            sell(name, cur_price, bot)
        if prev_price is not None:
            diff_percent = round(
                (cur_price - prev_price) / cur_price * 100, 1
                )
            if diff_percent * -1 > GOLDEN_FIGURE:
                buy(name, cur_price, bot)
        # тестовый вывод для отладки
        if name == 'TSLA':
            print(f'TSLA >> cur_price: {cur_price}, '
                  f'prev_price: {prev_price}')
            try:
                print(f'diff_percent: {diff_percent}%')
            except Exception:
                pass
            if TRADE.get(name) is not None:
                print(f'в портфеле по {TRADE.get(name)}')


def main():
    """Раз в установленный интервал отправляет запрос в интернеты и получает
       данные по выбранным тикерам. Собирает list CONS_DATA со значениями вида:
       {'OKTA': {0: '95.76'}
       и отправляет его вместе с порядковым номером итерации в get_data().
    """
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    welcome_msg = f'''запуск скрипта с параметрами:
    >> запрос котировок: каждые {RETRY_TIME} секунд
    >> динамика отслеживается за {INTERVAL_MINUTES} интервалов
    >> отслеживаемое движение: {GOLDEN_FIGURE}%
    >> целевая прибыль/убыток: {TARGET_PERCENT}%'''
    print(welcome_msg)
    count: int = 1
    prev_response = ''
    non_trade_count: int = 0
    while True:
        if non_trade_count > 60:
            count = 1
        response = requests.get(
            url=f'{URL_static}{make_urls_str()}', params=PARAMS
            )
        if response.text != prev_response:
            print(f'итерация {count}: скрипт запущен и получает данные')
            non_trade_count = 0
        else:
            non_trade_count += 1
            print(f'итерация {count}: новые данные не поступают '
                  f'{non_trade_count} мин.')
        for data in response.json()['data']:
            name = data['symbol']
            cur_price = data['data'][1]
            NAMES_LIST.add(name)
            DATA[name] = {count: cur_price}
        CONS_DATA.append(DATA.copy())
        get_data(CONS_DATA, count, bot)
        prev_response = response.text
        count += 1
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
