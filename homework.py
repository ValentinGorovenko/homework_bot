import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests
import telegram
from dotenv import load_dotenv

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
    tokens = {
        'practicum_token': PRACTICUM_TOKEN,
        'telegram_token': TELEGRAM_TOKEN,
        'telegram_chat_id': TELEGRAM_CHAT_ID,
        'endpoint': ENDPOINT,
    }
    for key, value in tokens.items():
        if value is None:
            logging.critical(f'{key} отсутствует')
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        logging.error('Ошибка при отправке сообщения')
    else:
        logging.debug('Сообщение успешно отправлено')
    pass


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}

    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        message = f'Ошибка API: {response.status_code}'
        logging.error(message)
        raise requests.exceptions.RequestException(message)


def check_response(response):
    """Проверяем ответ API на соответствие документации."""
    if isinstance(response, dict):
        if 'homeworks' in response:
            if isinstance(response.get('homeworks'), list):
                return response.get('homeworks')
            raise TypeError('API возвращает не список.')
        raise KeyError('Не найден ключ homeworks.')
    raise TypeError('API возвращает не словарь.')


def parse_status(homework):
    """Проверяет статус конкретной домашней работы."""
    if isinstance(homework, dict):
        if 'status' in homework:
            if 'homework_name' in homework:
                if isinstance(homework.get('status'), str):
                    homework_name = homework.get('homework_name')
                    homework_status = homework.get('status')
                    if homework_status in HOMEWORK_VERDICTS:
                        verdict = HOMEWORK_VERDICTS.get(homework_status)
                        return ('Изменился статус проверки работы '
                                f'"{homework_name}". {verdict}')
                    else:
                        raise Exception("Неизвестный статус работы")
                raise TypeError('status не str.')
            raise KeyError('В ответе нет ключа homework_name.')
        raise KeyError('В ответе нет ключа status.')
    raise KeyError('API возвращает не словарь.')


def main():
    """Основная логика работы бота."""
    logging.info('Бот запущен')
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time())
        while True:
            try:
                response_result = get_api_answer(timestamp)
                homeworks = check_response(response_result)
                logging.info("Список работ получен")
                if len(homeworks) > 0:
                    send_message(bot, parse_status(homeworks[0]))
                    timestamp = response_result['current_date']
                else:
                    logging.info("Новых заданий нет")
                time.sleep(RETRY_PERIOD)
            except Exception as error:
                message = f'Ошибка: {error}'
                send_message(bot, message)
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s, %(levelname)s, %(message)s',
    )
    handler = RotatingFileHandler(
        filename=f'{Path(__file__).stem}.log',
        maxBytes=50000000,
        backupCount=5,
        encoding='utf-8'
    )
    main()
