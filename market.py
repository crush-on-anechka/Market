from __future__ import annotations
from tinkoff.invest import Client, OrderDirection, OrderType  # MoneyValue
# from tinkoff.invest.services import MarketDataService
from dotenv import load_dotenv
import telegram
import requests
import json
import figi
import time
import urls
import os

load_dotenv()

TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID')
SANDBOX_TOKEN: str = os.getenv('SANDBOX_TOKEN')

PARAMS = {'fieldmap': 'indices.minimal'}
URL_static = 'https://api.investing.com/api/financialdata/table/list/'
SANDBOX_ID = 'd79541e3-7477-498b-a14a-71db19f7aafb'

DATA: list = {}
CONS_DATA: list = []

NAMES_LIST: set = set()
for name in urls.urls.keys():
    NAMES_LIST.add(name)

with open('trade.json', encoding='UTF-8') as file:
    try:
        TRADE = json.load(file)
    except Exception:
        TRADE = {}

GENERAL_PERCENT: float = 0
ROUND_VOLUME: int = 2
POSITION_LIMIT: int = 1000

RETRY_TIME = 60         #        60
INTERVAL_MINUTES = 20   #        20
GOLDEN_FIGURE = 3.1     # 2.1   3.1
TARGET_PERCENT = 1.7    # 1.1   1.7

WELCOME_MSG = f'''запуск скрипта с параметрами:
    >> запрос котировок: каждые {RETRY_TIME} секунд
    >> динамика отслеживается за {INTERVAL_MINUTES} интервалов
    >> отслеживаемое движение: {GOLDEN_FIGURE}%
    >> целевая прибыль/убыток: {TARGET_PERCENT}%
    >> Открытые позиции: {TRADE}'''


def tinkoff_portfolio(bot):
    # with Client(SANDBOX_TOKEN) as sandbox:
        # <----- открыть счет в песочнице ----->
        # sandbox.sandbox.open_sandbox_account()

        # <----- пополнить счет----->
        # sandbox.sandbox.sandbox_pay_in(
        #     account_id=SANDBOX_ID,
        #     amount=MoneyValue(units=-16985, currency='usd')
        # )

    with Client(SANDBOX_TOKEN) as sandbox:
        data = sandbox.sandbox.get_sandbox_positions(account_id=SANDBOX_ID)
        send_message(bot, 'Состав портфеля:')
        for dt in data.money:
            send_message(bot, f'{dt.currency}: {dt.units}')
        for pos in data.securities:
            for tck, fg in figi.figi.items():
                if fg == pos.figi:
                    send_message(bot, f'{tck}: {pos.balance} акций')


def get_tinkoff_last_prices():
    # with Client(SANDBOX_TOKEN) as sandbox:
    #     market_data = sandbox.market_data
    #     all_data = market_data.get_last_prices().last_prices
    #     cur_prices = {}
    #     for data in all_data:
    #         last_price = (data.price.units +
    #                       data.price.nano / 10**9)
    #         cur_prices[data.figi] = last_price
    #         print(cur_prices)
    #         break
    # return cur_prices
    pass


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
    TRADE[name] = cur_price
    buy_msg = f'{name}: покупка по {cur_price}'
    send_message(bot, buy_msg)
    result_msg = f'''>> Общий результат торговли: {round(GENERAL_PERCENT, ROUND_VOLUME)}%
>> Открытые позиции: {TRADE}'''
    send_message(bot, result_msg)


def buy_tinkoff(name, cur_price, bot):
    """Покупка в песочнице"""
    try:
        cur_figi = figi.figi[name]
    except KeyError:
        return 'Тикер не найден'
    quantity = int(round(POSITION_LIMIT / cur_price, 0))
    if quantity == 0:
        return f'{name} не куплена - высокая цена акции: {cur_price}'
    try:
        with Client(SANDBOX_TOKEN) as sandbox:
            sandbox.sandbox.post_sandbox_order(
                figi=cur_figi,
                quantity=quantity,
                account_id=SANDBOX_ID,
                order_id=str(time.time()*1000),
                direction=OrderDirection.ORDER_DIRECTION_BUY,
                order_type=OrderType.ORDER_TYPE_MARKET
            )
            data = sandbox.sandbox.get_sandbox_positions(account_id=SANDBOX_ID)
            buy(name, cur_price, bot)
            send_message(bot, 'Состав портфеля:')
            for dt in data.money:
                message = f'{dt.currency}: {dt.units}'
                send_message(bot, message)
            for pos in data.securities:
                for tck, fg in figi.figi.items():
                    if fg == pos.figi:
                        message = f'{tck}: {pos.balance} акций'
                        send_message(bot, message)
    except Exception as error:
        print(f'При покупке {name} возникла ошибка: {error}')


def sell(name, cur_price, bot):
    """Вычисляет разницу между текущей ценой и ценой, зафиксированной
       в словаре TRADE, убирает компанию из TRADE, прибавляет результат
       торговли к глобальном итогу и выводит инфо о сделке и итог в терминал.
    """
    result = - round(
        (TRADE.get(name) - cur_price) / cur_price * 100, ROUND_VOLUME
        )
    sell_msg = (f'{name}: продажа, результат: {result}% '
                f'({TRADE.get(name)} >> {cur_price})')
    send_message(bot, sell_msg)
    global GENERAL_PERCENT
    GENERAL_PERCENT += result
    trade_len = max([num + 1 for num, keys in enumerate(TRADE.keys())])
    trade_max_len: int = 0
    if trade_len > trade_max_len:
        trade_max_len = trade_len
    TRADE.pop(name)
    result_msg = f'''>> Общий результат торговли: {round(GENERAL_PERCENT, ROUND_VOLUME)}%
>> Макс. число одновременно открытых позиций: {trade_max_len}
>> Открытые позиции: {TRADE}'''
    send_message(bot, result_msg)


def sell_tinkoff(name, cur_price, bot):
    """Продажа в песочнице"""
    cur_figi = figi.figi.get(name)
    with Client(SANDBOX_TOKEN) as sandbox:
        data = sandbox.sandbox.get_sandbox_positions(account_id=SANDBOX_ID)
        for pos in data.securities:
            for tck, fg in figi.figi.items():
                if fg == pos.figi and tck == name:
                    quantity = pos.balance
        try:
            sandbox.sandbox.post_sandbox_order(
                figi=cur_figi,
                quantity=quantity,
                account_id=SANDBOX_ID,
                order_id=str(time.time()*1000),
                direction=OrderDirection.ORDER_DIRECTION_SELL,
                order_type=OrderType.ORDER_TYPE_MARKET
            )
            sell_msg = f'Продажа {quantity} акций {name}'
            portfolio_msg = f'Состав портфеля до продажи {name}:'
            send_message(bot, sell_msg)
            send_message(bot, portfolio_msg)
            for dt in data.money:
                message = f'{dt.currency}: {dt.units}'
                send_message(bot, message)
            for pos in data.securities:
                for tck, fg in figi.figi.items():
                    if fg == pos.figi:
                        message = f'{tck}: {pos.balance} акций'
                        send_message(bot, message)
        except Exception as error:
            print(f'При попытке продажи {name} что-то пошло не так: {error}')


def get_data(name, CONS_DATA: list[dict], count, bot):
    """Получает данные по каждой итерации из main, по каждой компании
       расчитывает текущую цену и цену на момент времени в прошлом за
       выбранный интервал.
       Если в словаре TRADE (заполняется в функции buy()) есть итерируемая
       компания - идет на sell().
       Если отрицательная разница между котировками превышает золотое
       число (цена падает) - buy() и выводит в терминал разницу котировок.
    """
    prev_count = count - INTERVAL_MINUTES
    prev_price = None
    to_buy = False
    data_list = [data[name] for data in CONS_DATA]
    for data in data_list:
        if data.get(count) is not None:
            cur_price = float(data.get(count))
        if data.get(prev_count) is not None:
            prev_price = float(data.get(prev_count))
    if prev_price is not None:
        diff_percent = round(
            (cur_price - prev_price) / cur_price * 100, ROUND_VOLUME
            )
        if diff_percent * -1 > GOLDEN_FIGURE:
            to_buy = True
            if name not in TRADE:
                buy_tinkoff(name, cur_price, bot)
    if (TRADE.get(name) is not None
            and abs(TRADE.get(name) - cur_price)
            / cur_price > TARGET_PERCENT / 100
            and to_buy is False):
        sell(name, cur_price, bot)
        sell_tinkoff(name, cur_price, bot)


def main():
    """Раз в установленный интервал отправляет запрос в интернеты и получает
       данные по выбранным тикерам. Собирает list CONS_DATA со значениями вида:
       {'OKTA': {0: '95.76'}, ...}
       и отправляет его вместе с порядковым номером итерации в get_data().
    """
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, WELCOME_MSG)
    tinkoff_portfolio(bot)
    prev_response = ''
    while True:
        with open('count_file.txt', 'r') as file:
            count: int = int(file.read())
        response = requests.get(
            url=f'{URL_static}{make_urls_str()}', params=PARAMS
            )
        if response.text != prev_response:
            print(f'успешная итерация {count}: скрипт получает свежие данные')
            with open('count_file.txt', 'w') as file:
                file.write(str(count + 1))
                file.close()
        else:
            print(f'итерация {count}: новые данные не поступают')
        for data in response.json()['data']:
            name = data['symbol']
            cur_price = data['data'][1]
            DATA[name] = {count: cur_price}
        CONS_DATA.append(DATA.copy())
        for name in NAMES_LIST:
            get_data(name, CONS_DATA, count, bot)
        with open('trade.json', 'w') as file:
            json.dump(TRADE, file)
            file.close()
        prev_response = response.text
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
