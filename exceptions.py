class ParseValueException(Exception):
    """Некорректный статус."""

    pass


class ErrorAnswerException(Exception):
    """Ошибка получения ответа."""

    pass


class EmptyResponseApiException(Exception):
    """Пустой ответ API."""

    pass
