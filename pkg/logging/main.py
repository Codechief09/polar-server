from enum import Enum
import logging  # <-- 1. loggingをインポート
import json

from flask import g


class LoggerLevel(Enum):
    INFO = logging.INFO
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    DEBUG = logging.DEBUG
    CRITICAL = logging.CRITICAL


def custom_log(message: str, level=LoggerLevel.INFO, exc_info=False) -> None:
    """
    トレースIDと任意のログレベルを使用してログを出力するカスタムロギング関数。
    exc_infoオプションをTrueに設定すると、トレースバック情報もログに含めることができます。
    """
    full_message = {
        "trace_id": g.trace_id,
        "message": message
    }

    if level == LoggerLevel.INFO:
        logging.info(json.dumps(full_message), exc_info=exc_info)
    elif level == LoggerLevel.ERROR:
        logging.error(json.dumps(full_message), exc_info=exc_info)
    elif level == LoggerLevel.WARNING:
        logging.warning(json.dumps(full_message), exc_info=exc_info)
    elif level == LoggerLevel.DEBUG:
        logging.debug(json.dumps(full_message), exc_info=exc_info)
    elif level == LoggerLevel.CRITICAL:
        logging.critical(json.dumps(full_message), exc_info=exc_info)
    else:
        logging.info(json.dumps(full_message), exc_info=exc_info)
