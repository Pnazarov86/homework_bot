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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
format = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')
handler.setFormatter(format)
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
        logger.error(message)
        raise APIAnswerException(message)
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if type(response) is not dict:
        logging.error('Ответ должен быть словарем')
        raise TypeError('Ответ должен быть словарем')
    elif 'homeworks' not in response:
        logging.error('Ключ homeworks отсутствует')
        raise KeyError('Ключ homeworks отсутствует')
    elif type(response['homeworks']) is not list:
        logging.error('homeworks должен быть списком!')
        raise TypeError('homeworks должен быть списком!')
    if response['homeworks'] == []:
        return {}
    return response.get('homeworks')[0]


def parse_status(homework):
    """Извлекает статус домашней работы."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
        verdict = HOMEWORK_VERDICTS[homework_status]
    except Exception as error:
        if homework_status not in HOMEWORK_VERDICTS.keys():
            logger.error(f'Неизвестный статус домашней работы: {error}')
            raise ValueError('Неизвестный статус домашней работы.')
        else:
            logger.debug('Новый статус отсутсвует.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError('Отсутствует токен')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework)
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
