import enum

import pydantic


class Operations(str, enum.Enum):
    mount = "mount"
    unmount = "unmount"


class CommandOperation(pydantic.BaseModel):
    operation: Operations
    device: str
