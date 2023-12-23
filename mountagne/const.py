import enum

import pydantic


DevicesSet = set[str]


class Operations(str, enum.Enum):
    mount = "mount"
    unmount = "unmount"


class CommandOperation(pydantic.BaseModel):
    operation: Operations
    device: str
