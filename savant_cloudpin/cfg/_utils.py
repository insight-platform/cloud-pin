import dataclasses
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

ENV_PREFIX = "CLOUDPIN"


def to_map_config(
    dataclass_config: Any, /, excluded: tuple[str, ...]
) -> dict[str, str | int]:
    return {
        key: val
        for key, val in asdict(dataclass_config).items()
        if isinstance(key, str) and isinstance(val, (str, int))
        if key not in excluded
    }


def drop_none_values[K](dct: Mapping[K, Any]) -> dict[K, Any]:
    result = dict[K, Any]()
    for key, val in dct.items():
        if isinstance(val, dict):
            result[key] = drop_none_values(val)
        elif val is not None:
            result[key] = val
    return result


def as_value_dict(obj: Any) -> dict[str, Any]:
    dct = dataclasses.asdict(obj)
    return drop_none_values(dct)


def env_override(
    obj: Any,
    default: str | None = None,
    prefix: str = ENV_PREFIX,
) -> Any:
    if isinstance(obj, type):
        raise ValueError("Instance is expected")
    updates = dict[str, Any]()
    for field in dataclasses.fields(obj):
        name, val = field.name, getattr(obj, field.name)
        env_name = f"{prefix}_{name.upper()}"
        match val:
            case str() | int() | float() if default is None:
                updates[name] = f"${{oc.env:{env_name},{val}}}"
            case str() | int() | float():
                updates[name] = f"${{oc.env:{env_name},{default}}}"
            case bool() if default is None:
                updates[name] = f"${{oc.env:{env_name},{str(val).lower()}}}"
            case bool():
                updates[name] = f"${{oc.env:{env_name},{default}}}"
            case None:
                continue
            case _:
                updates[name] = env_override(val, default, env_name)

    return dataclasses.replace(obj, **updates)
