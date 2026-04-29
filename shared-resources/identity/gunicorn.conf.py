import faulthandler
import logging
import sys
import threading


def post_fork(server, worker):
    faulthandler.enable(file=sys.stderr)

    _log = logging.getLogger("gunicorn.error")

    def _thread_exc_handler(args):
        _log.error(
            "Unhandled exception in background thread '%s'",
            args.thread.name if args.thread else "unknown",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_exc_handler

    def _unraisable_handler(unraisable):
        _log.error(
            "Unraisable exception: %s",
            unraisable.err_msg or unraisable.object,
            exc_info=(unraisable.exc_type, unraisable.exc_value, unraisable.exc_tb),
        )

    sys.unraisablehook = _unraisable_handler


def worker_exit(server, worker):
    print(
        f"worker_exit hook: pid={worker.pid} exitcode={getattr(worker, 'exitcode', 'unknown')}",
        file=sys.stderr,
        flush=True,
    )
    server.log.error(
        "worker_exit hook: pid=%s exitcode=%s",
        worker.pid,
        getattr(worker, "exitcode", "unknown"),
    )
