import logging
import os

# https://zenn.dev/dencyu/articles/2b58f669bcd473

log_path = '/var/log/raft-on-weekends/'
logger = logging.getLogger('raft')
logger.setLevel(logging.DEBUG)

format = "%(levelname)-9s  %(asctime)s [%(filename)s:%(lineno)d] %(message)s"

# filename = os.path.join(log_path, 'process.log')

# Streamハンドラクラスをインスタンス化
st_handler = logging.StreamHandler()
st_handler.setFormatter(logging.Formatter(format))

# Fileハンドラクラスをインスタンス化
# fl_handler = logging.FileHandler(filename=filename, encoding="utf-8")



logger.addHandler(st_handler)
# logger.addHandler(fl_handler)