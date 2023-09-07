import os
import sys
import time
from http import HTTPStatus

import logging
import requests
import telegram
from dotenv import load_dotenv

from exceptions import ErrorAnswerException, ParseValueException
from exceptions import EmptyResponseApiException

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

ENVIRONMENT_VARIABLES = (
    'PRACTICUM_TOKEN',
    'TELEGRAM_TOKEN',
    'TELEGRAM_CHAT_ID'
)


def check_tokens():
    """Проверка переменных окружения."""
    ret_val = True
    for variable in ENVIRONMENT_VARIABLES:
        if not globals()[variable]:
            logging.critical(f'Отсутствует обязательная переменная '
                             f'окружения:{variable}')
            ret_val = False
    return ret_val


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f"Отправлено сообщение {message}")
        return True
    except telegram.error.TelegramError as error:
        logging.error(error)
        return False


def get_api_answer(timestamp):
    """Получение ответа на запрос."""
    http_error_message = 'HTTP Error: {status_code}. '
    answer_message = (
        'Запрос: URL: URL={url}, headers: {headers}, params: {params}'
    )
    request_params = dict(url=ENDPOINT,
                          headers=HEADERS,
                          params={'from_date': timestamp}
                          )
    logging.debug(answer_message.format(**request_params))
    try:
        homework_statuses = requests.get(**request_params)
        if homework_statuses.status_code != HTTPStatus.OK:
            raise ErrorAnswerException(
                (http_error_message + answer_message).format(
                    status_code=homework_statuses.status_code,
                    **request_params
                )
            )
    except requests.RequestException as status_code:
        raise ErrorAnswerException(f'{http_error_message} {status_code}')

    return homework_statuses.json()


def check_response(response):
    """Проверка полученного ответа."""
    logging.debug(f"Проверка ответа {response}")
    error_message = 'Формат ответа API не соответствует.'
    if not isinstance(response, dict):
        raise TypeError(error_message)

    error_message = 'Отсутствует ключ ["homeworks"] в ответе API.'
    if 'homeworks' not in response:
        raise EmptyResponseApiException(error_message)

    error_message = 'Формат ответа API не соответствует.'
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(error_message)

    return homeworks


def parse_status(homework):
    """Получение статуса из ответа."""
    status = homework.get('status')
    homework_name = homework.get('homework_name')

    error_message = f'Неожиданный ответ: {homework}.'
    if 'homework_name' not in homework:
        raise ParseValueException(error_message)

    error_message = f'Неожиданный статус в ответе: {status}.'
    if status not in HOMEWORK_VERDICTS.keys():
        raise ParseValueException(error_message)
    verdict = HOMEWORK_VERDICTS[status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основной цикл опроса бота."""
    if not check_tokens():
        logging.critical('Аварийное завершение')
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    timestamp = 0
    previous_status = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                last_parse_status = parse_status(homeworks[0])
                if previous_status != last_parse_status:
                    if send_message(bot, last_parse_status):
                        timestamp = response.get('current_date', timestamp)
                        previous_status = last_parse_status
            else:
                logging.debug('Изменений нет')

        except EmptyResponseApiException as error:
            logging.exception(error)

        except Exception as error:
            logging.exception(error)
            if previous_status != error and send_message(bot, error):
                previous_status = error

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(f'{__file__}.log', encoding='utf-8')],
        format='%(asctime)s, %(levelname)s '
               '[%(filename)s:%(lineno)s - %(funcName)s() ]  '
               ' %(message)s'
    )
    main()
