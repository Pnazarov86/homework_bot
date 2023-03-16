import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Формирование сообщения для бота."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение успешно отправленно: {message}')
        return True
    except telegram.TelegramError as error:
        logging.error(f'Сообщение не отправленно: {error}')
        return False


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception:
        raise APIAnswerException('Ошибка подключения к API.')
    if response.status_code != HTTPStatus.OK:
        raise APIAnswerException(
            f'Неверный код ответа: {response.status_code}'
        )
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
    if 'homework_name' not in homework:
        raise KeyError('Ключ homework_name отсутствует.')
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise KeyError('Ключ status отсутствует.')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError('Неизвестный статус домашней работы.')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = 'Отсутствие обязательных переменных окружения!'
        logging.critical(error_message)
        sys.exit(error_message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    prev_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks_list = check_response(response)
            if not homeworks_list:
                logging.debug('Новый статус отсутствует.')
            else:
                status_message = parse_status(homeworks_list[0])
                if status_message != prev_message:
                    logging.debug(status_message)
                    if send_message(bot, status_message):
                        prev_message = status_message
                        timestamp = response.get('current_date', timestamp)
        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            if error_message != prev_message:
                logging.error(error_message)
                if send_message(bot, error_message):
                    prev_message = error_message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s',
        handlers=[
            RotatingFileHandler(
                'my_logger.log',
                encoding='utf-8',
                maxBytes=10000000,
                backupCount=5
            ),
            logging.StreamHandler(sys.stdout)
        ]
    )
    main()
