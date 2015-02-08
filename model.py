# -*- coding: utf-8 -*-
import os
import sys
import logging
import threading
import time
import pickle
import signal
from datetime import datetime, timedelta

import web

model_db_path = '/data/happytalk.model.db'
max_thread = 100000000000000
max_alive_time = timedelta(hours=24)

class TalkException(Exception):
    pass

def lockroot(func):
    def inner(*args, **kargs):
        try:
            root_lock.acquire()
            return func(*args, **kargs)
        finally:
            root_lock.release()
    return inner


class Model(object):
    def __init__(self):
        self.threads = []
        self.clientips = {}
        self.max_thread = 0
        self.max_user = 0

    @lockroot
    def check_safe(self, clientip, message):
        message = message.strip()
        if not message:
            raise TalkException(u'你到底吐还是不吐')
        if len(message) > 280:
            raise TalkException(u'你至于吐这么多吗')
        last_active_time = self.clientips.get(clientip)
        self.clientips[clientip] = datetime.now()

    @lockroot
    def insert_thread(self, clientip, message):
        user = self.get_user()  # RLock支持递归，可以放心调用
        logging.info("insert thread:%s %s", clientip, message)
        thread = web.storage(id=self.max_thread, user=user, message=message,
                             posttime=datetime.now())
        self.max_thread += 1
        self.threads.append(thread)

    @lockroot
    def get_user(self):
        user = web.cookies().get('user')
        if user:
            return user
        self.max_user += 1
        web.setcookie('user', self.max_user)
        return self.max_user

@lockroot
def save_model(signal, frame):
    logging.info("begin save model")
    with open(model_db_path, 'wb') as f:
        pickle.dump(model, f)
    logging.info("end save model")
    sys.exit(0)

@lockroot
def load_model():
    if not os.path.exists(model_db_path):
        logging.info("load new model")
        return Model()

    with open(model_db_path, 'rb') as f:
        model = pickle.load(f)
        logging.info("load exists model:%s %s", model.max_thread, model.max_user)
        return model

def load_minganci():
    logging.info("loading minganci")
    for line in open('./minganci.txt'):
        word = line.strip().decode('utf-8')
        if word:
            yield word

def minganci_filter(message):
    for word in minganci_list:
        if message.find(word) != -1:
            return word
    return None

model = None
minganci_list = None
root_lock = threading.RLock()

def init():
    global model, minganci_list, root_lock
    model = load_model()
    minganci_list = list(load_minganci())

    signal.signal(signal.SIGTERM, save_model)
    signal.signal(signal.SIGINT, save_model)
