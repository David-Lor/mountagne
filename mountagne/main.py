import atexit
import pathlib
import fnmatch
import contextlib
import subprocess

import jc
import watchdog.events
import watchdog.observers
import watchdog.observers.inotify
import watchdog.observers.polling

from .logger import logger
from .settings import settings


def main():
    App().run()


class App(watchdog.events.FileSystemEventHandler):
    def __init__(self):
        self.managed_devs: set[str] = set()  # devices names (names of directories from watchdir, usually labels)
        self.blkid_installed = self.is_command_installed(settings.blkid_path)

        self.observer = watchdog.observers.inotify.InotifyObserver()
        # self.observer = watchdog.observers.polling.PollingObserver()
        # self.observer = watchdog.observers.Observer()
        self.observer_event_handler = self
        self.observer.schedule(self, settings.watch_dev_dir, recursive=False)

        atexit.register(self.teardown)

    def run(self):
        logger.info(f"Running with settings: {settings.model_dump_json()}")

        if settings.automount_at_start and (settings.filter_allow or settings.filter_block):
            self.mount_all_filtered()

        self.observer.start()
        with contextlib.suppress(KeyboardInterrupt, InterruptedError):
            self.observer.join()

    def teardown(self):
        logger.info("Stopping...")
        self.observer.stop()
        if settings.unmount_at_exit:
            self.unmount_all()

        logger.info("Stopped")

    def mount_all_filtered(self):
        devices_root_path = settings.watch_dev_dir
        for dev_path in devices_root_path.iterdir():
            dev_name = dev_path.name
            if self.dev_passes_filters(dev_name):
                logger.info(f"Automounting device {dev_name}...")
                self.process_device_connected(dev_path, dev_name)

    def unmount_all(self):
        while self.managed_devs:
            dev_name = self.managed_devs.pop()
            self.unmount(dev_name)

    def on_created(self, event: watchdog.events.FileSystemEvent):
        event_path = pathlib.Path(event.src_path)
        dev_name = event_path.name
        self.process_device_connected(event_path, dev_name)

    def on_deleted(self, event: watchdog.events.FileSystemEvent):
        event_path = pathlib.Path(event.src_path)
        dev_name = event_path.name
        self.process_device_disconnected(event_path, dev_name)

    def process_device_connected(self, dev_path: pathlib.Path, dev_name: str):
        if not self.dev_passes_filters(dev_name):
            logger.info(f"Device {dev_name} connected, but excluded from configured filters")
            return
        if dev_name in self.managed_devs:
            logger.info(f"Device {dev_name} connected, but was already being managed")
            return

        logger.info(f"Device {dev_name} connected, mounting...")
        if self.mount(dev_path, dev_name):
            self.managed_devs.add(dev_name)

    def process_device_disconnected(self, dev_path: pathlib.Path, dev_name: str):
        if dev_name not in self.managed_devs:
            logger.debug(f"Device {dev_name} disconnected from {dev_path}, but not managed")
            return

        logger.info(f"Device {dev_name} disconnected, unmounting...")
        if self.unmount(dev_name):
            self.managed_devs.remove(dev_name)

    def mount(self, dev_path: pathlib.Path, dev_name: str) -> bool:
        mount_path = self.get_mount_path(dev_name)
        logger.debug(f"Mounting device {dev_path} into {mount_path}...")
        if mount_path.is_mount():
            logger.info(f"Mount path {mount_path} is already mounted")
            return True

        extra_args = list()
        if override_filesystem := self.get_filesystem_override_type(dev_path):
            extra_args.extend(["-t", override_filesystem])

        cmd = [
            "mount",
            *extra_args,
            dev_path.absolute().as_posix(),
            mount_path.absolute().as_posix(),
        ]
        mount_path.mkdir(exist_ok=True)

        code, output = self.exec(cmd)
        if code == 0:
            logger.info(f"Device {dev_name} successfully mounted in {mount_path}")
            return True

        logger.error(f"Device {dev_name} failed to be mounted in {mount_path} ({output})")
        return False

    @classmethod
    def unmount(cls, dev_name: str) -> bool:
        success = True
        mount_path = cls.get_mount_path(dev_name)
        logger.debug(f"Unmounting device {dev_name} from {mount_path}...")

        code, output = cls.exec(["umount", mount_path])
        if code == 0:
            logger.info(f"Unmounted {dev_name} from {mount_path}")
        else:
            if "not mounted" in output:
                logger.debug(f"Mount path {mount_path} not mounted")
            else:
                logger.warning(f"Failed unmounting {mount_path} ({output})")
                success = False

        if settings.remove_mountdirs_after_unmount:
            logger.debug(f"Removing directory {mount_path}...")
            try:
                mount_path.rmdir()
                logger.debug(f"Removed directory {mount_path}")
            except Exception as ex:
                logger.warning(f"Failed removing mountpoint directory {mount_path} ({ex})")

        return success

    @staticmethod
    def exec(cmd: list[str], **kwargs) -> tuple[int, str]:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
            stdout, stderr = proc.communicate()  # type: bytes, bytes
            output = f"{stdout.decode()}\n{stderr.decode()}".strip().replace("\n", "; ")
            return proc.returncode, output

        except Exception as ex:
            return -1, str(ex)

    def get_filesystem_override_type(self, dev_path: pathlib.Path) -> str | None:
        overrides = settings.filesystem_types_overrides
        if not overrides:
            return None
        if not self.blkid_installed:
            logger.warning("blkid is not installed, so filesystem cannot be overriden; using default")
            return None

        dev_original_fs_type = self.get_dev_filesystem_type(dev_path)
        if not dev_original_fs_type:
            return None

        if dev_override_fs_type := settings.filesystem_types_overrides.get(dev_original_fs_type):
            logger.debug(f"Filesystem for device in {dev_path} detected as {dev_original_fs_type}, "
                         f"overriden as {dev_override_fs_type}")
            return dev_override_fs_type

    def file_watcher_callback(self, line: str, is_mount: bool):
        if line.startswith("/"):
            dev_path = pathlib.Path(line)
        else:
            dev_path = pathlib.Path(settings.watch_dev_dir) / line
        dev_name = dev_path.name

        logger.info(f"Ondemand file received order for {'mounting' if is_mount else 'unmounting'} {dev_path}")

        if is_mount:
            self.process_device_connected(dev_path, dev_name)
        else:
            self.process_device_disconnected(dev_path, dev_name)

    @classmethod
    def get_dev_filesystem_type(cls, dev_path: pathlib.Path) -> str | None:
        cmd = [settings.blkid_path, dev_path]
        code, output = cls.exec(cmd)
        if code != 0:
            logger.error(f"Failed determining filesystem type from {dev_path}")
            return None

        try:
            dev_data = jc.parse("blkid", output)[0]
            return dev_data["type"]
        except Exception as ex:
            logger.error(f"Failed parsing blkid output for {dev_path} ({ex})")
            return None

    @classmethod
    def is_command_installed(cls, cmd: str) -> bool:
        code, _ = cls.exec(["which", cmd])
        return code == 0

    @staticmethod
    def get_mount_path(dev_name: str):
        return settings.mountpoints_base_dir / dev_name

    @staticmethod
    def dev_passes_filters(name: str) -> bool:
        if not any(fnmatch.fnmatch(name, allow_pattern) for allow_pattern in settings.filter_allow):
            return False

        if any(fnmatch.fnmatch(name, block_pattern) for block_pattern in settings.filter_block):
            return False

        return True
