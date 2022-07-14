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

RETRY_TIME: int = 5            # 60 = котировка запрашивается раз в минуту!
INTERVAL_MINUTES: int = 2      # 25 = кол-во интервалов мониторинга изменения
GOLDEN_FIGURE: float = 3.1      # 4.4 = на какое кол-во % мониторим изменение
TARGET_PERCENT: float = 2.0     # 2.2 = целевая прибыль/убыток по сделке в %

DATA: list = {}
CONS_DATA: list = []
NAMES_LIST = []
TRADE: dict = {}
GENERAL_PERCENT: float = 0


def send_message(bot, message):
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


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


def get_data(CONS_DATA: list[dict], count: int, bot):
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
    count: int = 1 - INTERVAL_MINUTES
    prev_response = ''
    was_offline = True
    while True:
        print(f'итерация: {count}')
        response = requests.get(
            url=f'{URL_static}{urls.urls_str_test}', params=PARAMS
            )
        if response.text != prev_response:
            if was_offline:
                count += INTERVAL_MINUTES
                print('скрипт запущен и получает данные')
            for data in response.json()['data']:
                name = data['symbol']
                cur_price = data['data'][1]
                NAMES_LIST.append(name)
                DATA[name] = {count: cur_price}
            CONS_DATA.append(DATA.copy())
            get_data(CONS_DATA, count, bot)
            count += 1
            prev_response = response.text
            was_offline = False
            time.sleep(RETRY_TIME)
        else:
            if not was_offline:
                idle_msg = 'котировки не поступают'
                print(idle_msg)
            was_offline = True
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'возникла ошибка - {error}')
        time.sleep(RETRY_TIME)
