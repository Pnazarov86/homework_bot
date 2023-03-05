import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import APIAnswerException

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

logging.basicConfig(
    level=logging.DEBUG,
    filename='my_logger.log',
    encoding='utf-8',
    format='%(asctime)s, %(levelname)s, %(message)s',
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if (
        PRACTICUM_TOKEN is None
        and TELEGRAM_TOKEN is None
        and TELEGRAM_CHAT_ID is None
    ):
        logger.critical('Отсутствие обязательных переменных окружения!')
        return False
    return True


def send_message(bot, message) -> None:
    """Формирование сообщения для бота."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение успешно отправленно: {message}')
    except Exception as error:
        logger.error(f'Сообщение не отправленно: {error}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception as error:
        message = f'Недоступность эндпоинта: {error}'
        raise APIAnswerException(message)
    if response.status_code != 200:
        raise APIAnswerException(message)
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ должен быть словарем')
    if 'homeworks' not in response:
        raise KeyError('Ключ homeworks отсутствует')
    if not isinstance(response['homeworks'], list):
        raise TypeError('homeworks должен быть списком!')
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
        verdict = HOMEWORK_VERDICTS[homework_status]
    except Exception as error:
        if 'homework_name' not in homework:
            raise KeyError(f'Ключ homework_name отсутствует: {error}')
        if 'status' not in homework:
            raise KeyError(f'Ключ status отсутствует: {error}')
        if not isinstance(homework_status, HOMEWORK_VERDICTS):
            raise ValueError(f'Неизвестный статус домашней работы: {error}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    prev_message = ''
    prev_error = ''
    while True:
        try:
            response = get_api_answer(timestamp - RETRY_PERIOD)
            homework = check_response(response)
            if len(homework) > 0:
                message = parse_status(homework[0])
            else:
                message = 'Новый статус отсутствует.'
            if message != prev_message:
                send_message(bot, message)
                prev_message = message
            else:
                logger.debug(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != prev_error:
                send_message(bot, message)
                prev_error = message
            else:
                logger.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
