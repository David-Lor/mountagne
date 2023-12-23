import abc
import contextlib
import threading
import json
import typing

import pydantic

from . import const
from .logger import logger
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
            try:
                self._run_loop()
            except Exception as ex:
                logger.error(f"Exception in {self.__class__.__name__} loop: {ex.__class__.__name__}: {ex}")
                self._stop_event.wait(5)

    @abc.abstractmethod
    def _run_loop(self):
        pass

    def stop(self):
        with self.stop_ctx():
            pass

    @contextlib.contextmanager
    def stop_ctx(self):
        self._stop_event.set()
        yield
        self._thread.join()

    def callback_devices_changed(self, devices_now: const.DevicesSet):
        pass

    def _callback_message_received(self, data: str | bytes | const.CommandOperation):
        if not isinstance(data, const.CommandOperation):
            data = const.CommandOperation.model_validate_json(data)

        for callback in self.callbacks_message_received:
            callback(data)


class RedisComm(BaseComm):

    def __init__(self):
        super().__init__()

        import redis
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password.get_secret_value() if settings.redis_password else None,
            db=settings.redis_db,
            **settings.redis_kwargs,
        )

        self.redis_pubsub = None
        if topic := settings.redis_topic_commands:
            self.redis_pubsub = self.redis.pubsub()
            self.redis_pubsub.subscribe(topic)
            logger.debug(f"Redis listening to commands (topic={topic})")

        logger.info("Redis started")

    def _run_loop(self):
        if not self.redis_pubsub:
            self._stop_event.wait()

        try:
            for message in self.redis_pubsub.listen():
                try:
                    data = message.get("data")
                    if not isinstance(data, bytes):
                        continue

                    self._callback_message_received(data)

                except Exception as ex:
                    logger.error(f"Exception processing Redis payload: {ex.__class__.__name__}: {ex}")

        except Exception as ex:
            # Ignore exceptions when closing mountagne
            if not self._stop_event.is_set():
                raise ex

    def callback_devices_changed(self, devices_now: const.DevicesSet):
        topic = settings.redis_topic_status
        if not topic:
            return

        try:
            data = json.dumps({"devices": list(devices_now)})
            logger.debug(f"Redis publish (topic={topic}): {data}")
            self.redis.publish(
                channel=topic,
                message=data,
            )

        except Exception as ex:
            logger.warning(f"Exception publishing Redis: {ex.__class__.__name__}: {ex}")

    def stop(self):
        with self.stop_ctx():
            if self.redis_pubsub:
                self.redis_pubsub.close()
            self.redis.close()
        logger.info("Redis stopped")


class RestComm(BaseComm):

    def __init__(self):
        super().__init__()

        import asyncio
        import uvicorn
        import fastapi

        self.devices_cache: const.DevicesSet = set()
        self.fastapi = fastapi
        self.app = fastapi.FastAPI(
            title=settings.http_app_name,
        )

        # TODO Create a wrapper logger to send uvicorn logs to mountagne logger
        #   https://github.com/tiangolo/fastapi/discussions/7457#discussioncomment-5141102
        config = uvicorn.Config(
            app=self.app,
            host=settings.http_host,
            port=settings.http_port,
        )
        config.setup_event_loop()

        self._setup_endpoints()
        self.server = uvicorn.Server(config=config)
        self.loop = asyncio.get_event_loop()

    def _run_loop(self):
        try:
            self.loop.run_until_complete(self.server.serve())
        except RuntimeError as ex:
            if "Event loop stopped before Future completed" not in str(ex):
                raise ex

    def stop(self):
        with self.stop_ctx():
            self.loop.stop()
        logger.info("REST Server stopped")

    def callback_devices_changed(self, devices_now: const.DevicesSet):
        self.devices_cache = devices_now

    def _setup_endpoints(self):
        @self.app.post("/mount/{device_name}")
        def mount(device_name: str):
            return self._operation_handler(operation=const.Operations.mount, device_name=device_name)

        @self.app.post("/unmount/{device_name}")
        def unmount(device_name: str):
            return self._operation_handler(operation=const.Operations.unmount, device_name=device_name)

        @self.app.get("/devices")
        def get_devices():
            return self.DevicesResponse(devices=self.devices_cache)

    class OperationResponse(pydantic.BaseModel):
        success: bool
        message: str = ""

    class DevicesResponse(pydantic.BaseModel):
        devices: const.DevicesSet

    def _operation_handler(self, operation: const.Operations, device_name: str):
        import fastapi

        data = const.CommandOperation(
            operation=operation,
            device=device_name,
        )

        try:
            self._callback_message_received(data)
            response_body = self.OperationResponse(success=True)
            return fastapi.responses.JSONResponse(status_code=200, content=response_body.model_dump())

        except Exception as ex:
            response_body = self.OperationResponse(
                success=False,
                message=f"{ex.__class__.__name__}: {ex}"
            )
            return fastapi.responses.JSONResponse(status_code=500, content=response_body.model_dump())
