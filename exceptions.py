

class MissiningKeyException(Exception):
    """Отсутствует информация по ключу в ответе."""

    pass


class TelegramAnyErrorException(Exception):
    """Возможные сбои в работе телеграм."""

    pass
