from typing import Literal

type ConnectDir = Literal["bind", "connect"]
type ConnectDirPair = tuple[ConnectDir, ConnectDir]
type SocketType = Literal["tcp", "ipc"]


DIR_OPPOSITES: dict[ConnectDir, ConnectDir] = {
    "bind": "connect",
    "connect": "bind",
}


def opposite_dir(dir: ConnectDir | str) -> ConnectDir:
    if dir not in ("bind", "connect"):
        raise ValueError(f"Invalid connection direction {dir}")
    return DIR_OPPOSITES[dir]


def opposite_dir_url(url: str) -> str:
    dir, common_url = url.split(":", 1)
    return f"{opposite_dir(dir)}:{common_url}"
