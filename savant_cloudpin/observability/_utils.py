from collections.abc import AsyncGenerator, Callable
from functools import wraps
from typing import Concatenate


async def noop_agen() -> AsyncGenerator:
    yield


type CallableWithArg[T, **P, R] = Callable[Concatenate[T, P], R]


def none_arg_returns[T, **P, R](
    return_value: Callable[[], R],
) -> Callable[[CallableWithArg[T, P, R]], CallableWithArg[T | None, P, R]]:
    def decorate(func: CallableWithArg[T, P, R]) -> CallableWithArg[T | None, P, R]:
        @wraps(func)
        def wrapper(arg: T | None, *args: P.args, **kwargs: P.kwargs) -> R:
            if arg is None:
                return return_value()
            return func(arg, *args, **kwargs)

        return wrapper

    return decorate
