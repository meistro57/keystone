# filename: app/utils/log.py
import logging
import os
import sys
from datetime import datetime

import config


def get_logger(name: str = "keystone") -> logging.Logger:
    os.makedirs(config.LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s │ %(levelname)-7s │ %(message)s", "%H:%M:%S")

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    logfile = os.path.join(config.LOG_DIR, f"keystone-{datetime.now():%Y%m%d-%H%M%S}.log")
    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger
