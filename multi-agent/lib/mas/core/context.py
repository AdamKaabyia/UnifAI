from contextvars import ContextVar
from .run_context import RunContext

_current: ContextVar[RunContext] = ContextVar("run_context")


def set_current_context(ctx: RunContext):
    _current.set(ctx)


def get_current_context() -> RunContext:
    return _current.get()
