import dataclasses
import operator
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any, cast

from omegaconf import DictConfig

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


def env_override[T](
    obj: T,
    default: str | None = None,
    prefix: str = ENV_PREFIX,
) -> T:
    if isinstance(obj, type):
        raise ValueError("Instance is expected")
    updates = dict[str, Any]()
    if dataclasses.is_dataclass(obj):
        items = ((f.name, getattr(obj, f.name)) for f in dataclasses.fields(obj))
    elif isinstance(obj, dict):
        items = obj.items()
    else:
        raise TypeError("Unsupported type")
    for name, val in items:
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

    if isinstance(obj, dict):
        obj.update(**updates)
        return cast(T, obj)
    return dataclasses.replace(obj, **updates)


def scrape_sensitive_keys(obj: Any, sensitive_keys: Sequence[str]) -> None:
    if dataclasses.is_dataclass(obj):
        items = ((f.name, getattr(obj, f.name)) for f in dataclasses.fields(obj))
        setkey = setattr
    elif isinstance(obj, (dict, DictConfig)):
        items = obj.items()
        setkey = operator.setitem
    else:
        raise TypeError(f"Unsupported type {type(obj)}")

    for key, val in items:
        match val:
            case str() if isinstance(key, str) and key in sensitive_keys:
                setkey(obj, key, "*****")
            case int() if isinstance(key, str) and key in sensitive_keys:
                setkey(obj, key, 0)
            case str() | int() | float() | bool() | None:
                continue
            case _:
                scrape_sensitive_keys(val, sensitive_keys)
