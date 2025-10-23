from dataclasses import asdict
from typing import Any


def to_map_config(
    dataclass_config: Any, /, excluded: tuple[str, ...]
) -> dict[str, str | int]:
    return {
        key: val
        for key, val in asdict(dataclass_config).items()
        if isinstance(key, str) and isinstance(val, (str, int))
        if key not in excluded
    }
