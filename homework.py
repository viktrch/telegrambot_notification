import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import MissiningKeyException, TelegramAnyErrorException

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    logging.info('Проверка переменных окружения...')
    env_variables = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID}
    for key, value in env_variables.items():
        if value is None:
            logging.critical(
                'Отсутствует обязательная переменная окружения: '
                f'<<{key}>>\nПрограмма принудительно остановлена.')
            sys.exit('Критическая ошибка, выполнение программы остановлено.')
    logging.info('Переменные окружения на месте!')


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.info('Попытка отправить сообщение в телеграмм...')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот успешно отправил сообщение: {message}.')
    except telegram.TelegramError as error:
        logging.error(f'Сбой отправки сообщения в Telegram: {error}')
        raise TelegramAnyErrorException('Сбой в работе Telegram')


def get_api_answer(timestamp):
    """Возвращает ответ от API в формате dict."""
    payload = {'from_date': timestamp}
    try:
        logging.info('Делаю запрос к ENDPOINT...')
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            logging.error(
                f'Эндпойнт {ENDPOINT} недоступен, '
                f'код ответа API: {response.status_code}')
            raise ConnectionError('Ошибка связи с Эндпойнт.')
    except requests.RequestException as error:
        raise ConnectionError(f'Прочие ошибки запроса: {error}')
    else:
        logging.info('Ответ успешно получен.')
        return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logging.info('Проверка корректности данных полученных от API...')
    if not isinstance(response, dict):
        raise TypeError('Не тот тип данных. Должен быть "dict"')
    if not response.get('homeworks'):
        raise MissiningKeyException('Нет данных о домашке.')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Не тот тип данных. Должен быть "list"')
    if not isinstance(response.get('homeworks')[0], dict):
        raise TypeError('Не тот тип данных. Должен быть "dict"')


def parse_status(homework):
    """Извлекает из информации о конкретной домашкой статус этой работы."""
    logging.info('Извлекаю информацию из ответа API...')
    if not homework.get('homework_name'):
        raise KeyError('Нет ключа "homework_name".')
    else:
        homework_name = homework.get('homework_name')
    if homework.get('status') not in HOMEWORK_VERDICTS:
        raise KeyError('Неожиданный статус домашней работы')
    else:
        verdict = HOMEWORK_VERDICTS[homework.get('status')]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD
    logging.debug('Бот запущен.')
    send_message(bot, 'Я буду инфорировать о статусе проверки твоей домашки.')

    saved_homework_status = ''
    saved_error_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')

        except MissiningKeyException as error:
            message = f'Работа пока не на проверке: {error}'
            logging.info(message)
            if message != saved_error_message:
                send_message(bot, message)
                saved_error_message = message

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != saved_error_message:
                send_message(bot, message)
                saved_error_message = message
        else:
            message = parse_status(homeworks[0])
            if saved_homework_status == message:
                logging.debug('Статус домашки не изменился.')
            else:
                send_message(bot, message)
                saved_homework_status = message
        finally:
            logging.debug('Делаю паузу 10 минут.')
            time.sleep(RETRY_PERIOD)
            logging.debug('Проверяю снова...')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, [%(levelname)s], <%(funcName)s>, %(message)s',
        stream=sys.stdout,
    )
    logging.getLogger('urllib3').setLevel('ERROR')
    logging.getLogger('telegram').setLevel('ERROR')
    main()
