import os
import pathlib

import pydantic_settings

ENV_FILE = os.getenv("ENV_FILE")


class Settings(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_file=ENV_FILE, env_file_encoding='utf-8')

    mountpoints_base_dir: pathlib.Path
    watch_dev_dir: pathlib.Path = "/dev/disk/by-label"
    filter_allow: list[str] = []
    filter_block: list[str] = []
    filesystem_types_overrides: dict[str, str] = {}
    automount_at_start: bool = False
    unmount_at_exit: bool = True
    remove_mountdirs_after_unmount: bool = True
    blkid_path: str = "blkid"


settings = Settings()
