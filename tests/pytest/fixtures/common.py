
import typing

import decorator


def log_exceptions(decorated_fn: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:

    def fn_decorator(
        original_fn: typing.Callable[..., typing.Any], *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Any:
        try:
            return original_fn(*args, **kwargs)
        except Exception as e:
            print(f'Exception :: {decorated_fn} :: {e.__class__.__name__} :: {e}')
            raise

    return decorator.decorator(fn_decorator)(decorated_fn)  # type: ignore[no-any-return, no-untyped-call]
