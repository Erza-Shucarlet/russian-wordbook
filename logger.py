"""
俄语单词本 — 日志系统
"""

import logging
import os

LOG_DIR = os.path.join(os.path.expanduser('~'), '.russian-wordbook')
LOG_FILE = os.path.join(LOG_DIR, 'app.log')

_logger = None


def get_logger(name='wordbook'):
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(LOG_DIR, exist_ok=True)

    _logger = logging.getLogger(name)
    _logger.setLevel(logging.DEBUG)

    # 文件输出
    fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    _logger.addHandler(fh)

    # 控制台也输出
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    _logger.addHandler(ch)

    return _logger


def info(msg): get_logger().info(msg)
def warn(msg): get_logger().warning(msg)
def error(msg): get_logger().error(msg)
def debug(msg): get_logger().debug(msg)
