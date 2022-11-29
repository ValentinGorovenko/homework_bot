import logging
import os
import sys
import time
from http import HTTPStatus

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
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        logging.error('Ошибка при отправке сообщения')
    else:
        logging.debug('Сообщение успешно отправлено')


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
    if not isinstance(response, dict):
        raise TypeError('API возвращает не словарь.')

    if 'homeworks' not in response:
        raise KeyError('Не найден ключ homeworks.')

    if not isinstance(response.get('homeworks'), list):
        raise TypeError('API возвращает не список.')

    return response.get('homeworks')


def parse_status(homework):
    """Проверяет статус конкретной домашней работы."""
    if not isinstance(homework, dict):
        raise TypeError('API возвращает не словарь.')

    if 'status' not in homework:
        raise KeyError('В ответе нет ключа status.')

    if 'homework_name' not in homework:
        raise KeyError('В ответе нет ключа homework_name.')

    if not isinstance(homework.get('status'), str):
        raise TypeError('status не str.')

    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise NameError('Неизвестный статус работы')

    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return ('Изменился статус проверки работы '
            f'"{homework_name}". {verdict}')


def main():
    """Основная логика работы бота."""
    logging.info('Бот запущен')
    if not check_tokens():
        msg = 'Отсутствует одна или несколько переменных окружения'
        logging.critical(msg)
        sys.exit(msg)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            logging.info('Список работ получен')
            if len(homeworks) > 0:
                send_message(bot, parse_status(homeworks[0]))
                timestamp = response['current_date']
            else:
                logging.info('Новых заданий нет')
        except Exception as error:
            message = f'Ошибка: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format=(
            '%(asctime)s [%(levelname)s] | '
            '(%(filename)s).%(funcName)s:%(lineno)d | %(message)s'
        ),
    )
    main()
