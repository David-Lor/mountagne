import abc
import contextlib
import threading
import typing

import redis

from . import const
from .settings import settings


CallbackMsgReceived = typing.Callable[[const.CommandOperation], None]


class BaseComm(abc.ABC):

    def __init__(self):
        self._thread = threading.Thread(target=self.run, name=self.__class__.__name__, daemon=True)
        self._stop_event = threading.Event()
        self.callbacks_message_received: list[CallbackMsgReceived] = list()

    def start(self):
        self._thread.start()

    def run(self):
        while not self._stop_event.is_set():
            self._run_loop()

    @abc.abstractmethod
    def _run_loop(self):
        pass

    def stop(self):
        with self.stop_ctx:
            pass

    @contextlib.contextmanager
    def stop_ctx(self):
        self._stop_event.set()
        yield
        self._thread.join()

    def _callback_message_received(self, data: str | bytes):
        payload = const.CommandOperation.model_validate_json(data)
        for callback in self.callbacks_message_received:
            callback(payload)


class RedisComm(BaseComm):

    def __init__(self):
        super().__init__()
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password.get_secret_value() if settings.redis_password else None,
            db=settings.redis_db,
            **settings.redis_kwargs,
        )
        self.redis_pubsub = self.redis.pubsub()
        self.redis_pubsub.subscribe(settings.redis_topic_commands)
        print("Redis start")

    def _run_loop(self):
        for message in self.redis_pubsub.listen():
            try:
                data = message.get("data")
                if not isinstance(data, bytes):
                    continue

                self._callback_message_received(data)

            except Exception as ex:
                print(ex)

    def stop(self):
        with self.stop_ctx():
            # TODO main loop failing on close
            self.redis_pubsub.close()
            self.redis.close()
        print("Redis stop")
