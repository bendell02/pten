import logging
import os
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 默认日志文件名跟随包名，避免硬编码；相对 CWD 解析
DEFAULT_LOG_PATH = __name__ + ".log"
# 当前文件 handler 实际写入的绝对路径，用于避免重复配置
_current_log_path = None


class LogColors:
    DEBUG = "\033[96m"
    INFO = "\033[92m"
    WARNING = "\033[93m"
    ERROR = "\033[91m"
    CRITICAL = "\033[41m\033[97m"
    RESET = "\033[0m"


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        level_color = {
            logging.DEBUG: LogColors.DEBUG,
            logging.INFO: LogColors.INFO,
            logging.WARNING: LogColors.WARNING,
            logging.ERROR: LogColors.ERROR,
            logging.CRITICAL: LogColors.CRITICAL,
        }.get(record.levelno, LogColors.RESET)

        message = super().format(record)
        return f"{level_color}{message}{LogColors.RESET}"


_console_formatter = ColoredFormatter(
    "%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d:%(funcName)s | %(message)s"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(_console_formatter)

_file_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d:%(funcName)s | %(message)s"
)
_MAX_BYTES = 30 * 1024 * 1024  # 30MB
_BACKUP_COUNT = 3


def _set_file_handler(path):
    """将文件 handler 替换为写入指定路径，返回实际使用的绝对路径；路径无效时回退默认值。"""
    for h in list(logger.handlers):
        if isinstance(h, RotatingFileHandler):
            logger.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass
    try:
        fh = RotatingFileHandler(path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT)
    except Exception:
        # 路径不可用（目录不存在、无权限等）时回退到默认路径，保证日志不丢
        path = DEFAULT_LOG_PATH
        fh = RotatingFileHandler(path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT)
    fh.setFormatter(_file_formatter)
    logger.addHandler(fh)
    return os.path.abspath(path)


def setup_logging(log_path=None):
    """配置日志文件 handler。

    :param log_path: 显式指定的日志文件路径。为空时使用默认值 ``<package>.log``（相对 CWD）。
    日志初始化绝不能阻断 import pten，任何异常都回退到默认值。
    """
    global _current_log_path
    target = log_path or DEFAULT_LOG_PATH
    target_abs = os.path.abspath(target)
    if target_abs == _current_log_path:
        return  # 已是该路径，跳过重复配置
    _current_log_path = _set_file_handler(target)


# import 时用默认路径初始化文件 handler，console handler 始终附加
setup_logging()
logger.addHandler(console_handler)
