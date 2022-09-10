from __future__ import annotations
from tinkoff.invest import Client, OrderDirection, OrderType
# MoneyValue
# from tinkoff.invest.services import MarketDataService
from dotenv import load_dotenv
from pprint import pprint
import calendar
import datetime
import telegram
import requests
import figi
import time
import urls
import os

load_dotenv()

TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID')
# <-----------------------------\/\/\/--------------------------------->
SANDBOX_TOKEN: str = os.getenv('SANDBOX_TOKEN')
# TINKOFF_TOKEN: str = os.getenv('TINKOFF_TOKEN')
# <-----------------------------/\/\/\--------------------------------->

PARAMS = {'fieldmap': 'indices.minimal'}
URL_static = 'https://api.investing.com/api/financialdata/table/list/'
# <-----------------------------\/\/\/--------------------------------->
SANDBOX_ID = '0f16a13f-91d1-4a0f-8ec7-d0971aa3324d'
# TINKOFF_ID = ''
# <-----------------------------/\/\/\--------------------------------->

DATA: list = {}
CONS_DATA: list = []

TRADE: dict = {}
NAMES_LIST: set = set()
for name in urls.urls.keys():
    NAMES_LIST.add(name)

GENERAL_PERCENT: float = 0
ROUND_VOLUME: int = 2
POSITION_LIMIT: int = 250
TRADE_MAX_LEN: int = 40
NANO: int = 10**9

RETRY_TIME_SEC = 60
INTERVAL_MINUTES = 20
GOLDEN_FIGURE = 3.1     # 2.1
TARGET_PERCENT = 1.7    # 1.1

OFFDAY_SEC = 172800

WELCOME_MSG = f'''запуск скрипта с параметрами:
    >> запрос котировок: каждые {RETRY_TIME_SEC} секунд
    >> динамика отслеживается за {INTERVAL_MINUTES} интервалов
    >> отслеживаемое движение: {GOLDEN_FIGURE}%
    >> целевая прибыль/убыток: {TARGET_PERCENT}%'''


def tinkoff_portfolio(bot):

    now = datetime.datetime.now()
    start = now - datetime.timedelta(weeks=2)
    # <-----------------------------\/\/\/--------------------------------->
    with Client(SANDBOX_TOKEN) as sandbox:
        # portfolio = tinkoff.operations.get_portfolio()
        portfolio = sandbox.sandbox.get_sandbox_portfolio(
            account_id=SANDBOX_ID
    # <-----------------------------/\/\/\--------------------------------->v
            )
        portf_list = []
        for pos in portfolio.positions:
            portf_list.append(pos.figi)
    # <-----------------------------\/\/\/--------------------------------->
        # data = tinkoff.operations.get_operations()
        data = sandbox.sandbox.get_sandbox_operations(
            account_id=SANDBOX_ID,
    # <-----------------------------/\/\/\--------------------------------->
            from_=start,
            to=now
            )
        for operation in data.operations:
            for tck, fg in figi.figi.items():
                if (fg == operation.figi
                   and fg in portf_list
                   and operation.type == 'Покупка ЦБ'):
                    price = (operation.price.units +
                             operation.price.nano / NANO)
                    TRADE[tck] = round(price, ROUND_VOLUME)
        shares_in_rub = (portfolio.total_amount_shares.units
                         + portfolio.total_amount_shares.nano / NANO)
# <-----------------------------\/\/\/--------------------------------->
        usdrub = (portfolio.positions[0].current_price.units
        # usdrub = (portfolio.positions[1].average_position_price.units
                  + portfolio.positions[0].current_price.nano / NANO)
                #   + portfolio.positions[1].average_position_price.nano / NANO)
        shares_in_usd = round(shares_in_rub / usdrub, ROUND_VOLUME)
        send_message(
            bot, f'Баланс, usd: {portfolio.positions[0].quantity.units}')
            # bot, f'Баланс, usd: {portfolio.positions[1].quantity.units}')
# <-----------------------------/\/\/\--------------------------------->
        send_message(bot, f'Стоимость акций в портфеле, usd: {shares_in_usd}')
        send_message(bot, f'Состав портфеля: {TRADE}')


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
    buy_msg = f'''{name}: покупка по {cur_price}
Открытые позиции: {TRADE}'''
    send_message(bot, buy_msg)


def buy_tinkoff(name, cur_price, bot):
    """Покупка в песочнице"""
    try:
        cur_figi = figi.figi[name]
    except KeyError:
        return 'Тикер не найден'
    quantity = int(round(POSITION_LIMIT / cur_price, 0))
    if quantity == 0:
        high_price_msg = f'{name} не куплена - высокая цена акции: {cur_price}'
        return send_message(bot, high_price_msg)
    try:
    # <-----------------------------\/\/\/--------------------------------->
        with Client(SANDBOX_TOKEN) as sandbox:
            # tinkoff.orders.post_order
            sandbox.sandbox.post_sandbox_order(
                figi=cur_figi,
                quantity=quantity,
                account_id=SANDBOX_ID,
    # <-----------------------------/\/\/\--------------------------------->
                order_id=str(time.time()*1000),
                direction=OrderDirection.ORDER_DIRECTION_BUY,
                order_type=OrderType.ORDER_TYPE_MARKET
            )
            buy(name, cur_price, bot)
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
    TRADE.pop(name)
    result_msg = f'''>> P&L на капитал: {round(GENERAL_PERCENT / TRADE_MAX_LEN, ROUND_VOLUME)}%
>> Открытые позиции: {TRADE}'''
    send_message(bot, result_msg)


def sell_tinkoff(name, cur_price, bot):
    """Продажа в песочнице"""
    cur_figi = figi.figi.get(name)
    # <-----------------------------\/\/\/--------------------------------->
    with Client(SANDBOX_TOKEN) as sandbox:
        # data = tinkoff.operations.get_positions()
        data = sandbox.sandbox.get_sandbox_positions(account_id=SANDBOX_ID)
    # <-----------------------------/\/\/\--------------------------------->
        for pos in data.securities:
            for tck, fg in figi.figi.items():
                if fg == pos.figi and tck == name:
                    quantity = pos.balance
        try:
    # <-----------------------------\/\/\/--------------------------------->
            # tinkoff.orders.post_order
            sandbox.sandbox.post_sandbox_order(
                figi=cur_figi,
                quantity=quantity,
                account_id=SANDBOX_ID,
    # <-----------------------------/\/\/\--------------------------------->
                order_id=str(time.time()*1000),
                direction=OrderDirection.ORDER_DIRECTION_SELL,
                order_type=OrderType.ORDER_TYPE_MARKET
            )
    # <-----------------------------\/\/\/--------check_this!!!---------------->
            send_message(bot, f'Баланс, usd: {data.money[0].units}')
    # <-----------------------------/\/\/\--------------------------------->
        except Exception as error:
            print(f'При попытке продажи {name} что-то пошло не так: {error}')


def calculation(name, CONS_DATA: list[dict], voo, count, bot):
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
    voo_msg = f'S&P500 изменение за день: {voo}%'
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
            if name not in TRADE and len(TRADE) < TRADE_MAX_LEN:
                send_message(bot, voo_msg)
                buy_tinkoff(name, cur_price, bot)
    if (TRADE.get(name) is not None
            and abs(TRADE.get(name) - cur_price)
            / cur_price > TARGET_PERCENT / 100
            and to_buy is False):
        send_message(bot, voo_msg)
        sell(name, cur_price, bot)
        sell_tinkoff(name, cur_price, bot)


def get_consolidated_data(count, response):
    try:
        for data in response.json().get('data'):
            if data['symbol'] == 'VOO':
                voo = data['data'][3]
            name = data['symbol']
            cur_price = data['data'][1]
            DATA[name] = {count: cur_price}
    except AttributeError as error:
        print(f'ошибка в полученных данных: {error}')
    CONS_DATA.append(DATA.copy())
    return voo


def main():
    """Раз в установленный интервал отправляет запрос в интернеты и получает
       данные по выбранным тикерам. Собирает list CONS_DATA со значениями вида:
       {'OKTA': {0: '95.76'}, ...}
       и отправляет его вместе с порядковым номером итерации в calculation().
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
        else:
            print(f'итерация {count}: новые данные не поступают')
        voo = get_consolidated_data(count, response)
        for name in NAMES_LIST:
            calculation(name, CONS_DATA, voo, count, bot)
        prev_response = response.text
        current_weekday = datetime.date.weekday(datetime.date.today())
        if current_weekday == 5:
            send_message(bot, 'Суббота. Увидимся через двое суток')
            time.sleep(OFFDAY_SEC)
            send_message(bot, 'Возвращаюсь к работе')
        time.sleep(RETRY_TIME_SEC)


if __name__ == '__main__':
    main()
