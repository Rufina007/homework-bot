import http
import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telebot import apihelper, TeleBot

from exceptions import (
    InvalidResponseError, UnknownStatusError, MissingTokenError
)

load_dotenv()

logger = logging.getLogger(__name__)

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
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    missing = []
    for name, value in tokens.items():
        if not value:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: {name}'
            )
            missing.append(name)
    if missing:
        raise MissingTokenError(f'Отсутствуют переменные: {missing}')


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение: {message} успешно отправлено.')
        return True
    except (apihelper.ApiException, requests.RequestException) as error:
        logger.error(f'Сбой при отправке сообщения: {error}')
        return False


def get_api_answer(timestamp):
    """Делает запрос к API Практикума и возвращает ответ."""
    payload = {'from_date': timestamp}
    logger.debug(f'Начало запроса к API: {ENDPOINT}')
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=payload
        )
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка при запросе к API: {error}')
    if response.status_code != http.HTTPStatus.OK:
        raise InvalidResponseError(
            f'Получен неожиданный статус-код: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ожидался словарь, получен {type(response)}'
        )
    if 'homeworks' not in response:
        raise InvalidResponseError('В ответе API нет ключа homeworks')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'Ожидался список, получен {type(homeworks)}'
        )
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы и возвращает строку для Telegram."""
    if not isinstance(homework, dict):
        raise TypeError(
            f'Ожидался словарь, получен {type(homework)}'
        )
    if 'homework_name' not in homework:
        raise InvalidResponseError(
            'В ответе API домашки нет ключа homework_name'
        )
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise UnknownStatusError(
            f'Неизвестный статус домашней работы: {status}'
        )
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    # Создаем объект класса бота.
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    prev_report = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if send_message(bot, message):
                    timestamp = response.get('current_date', timestamp)
                    prev_report = None
            else:
                logger.debug('Нет новых статусов')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != prev_report:
                send_message(bot, message)
                prev_report = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        level=logging.DEBUG,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    try:
        main()
    except Exception as error:
        sys.exit(f'Программа завершена с ошибкой: {error}')
