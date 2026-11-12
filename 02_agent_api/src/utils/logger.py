import logging
from pythonjsonlogger import jsonlogger


def get_logger(name: str = __name__) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        from src.utils.pii_log_filter import PIIRedactionFilter

        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s"
        )
        handler.setFormatter(formatter)
        handler.addFilter(PIIRedactionFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger