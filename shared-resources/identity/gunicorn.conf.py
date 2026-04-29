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
    # Called in the CHILD process (only if worker reaches the try block in spawn_worker)
    print(
        f"worker_exit hook (child): pid={worker.pid} exitcode={getattr(worker, 'exitcode', 'unknown')}",
        file=sys.stderr,
        flush=True,
    )
    server.log.error(
        "worker_exit hook (child): pid=%s exitcode=%s",
        worker.pid,
        getattr(worker, "exitcode", "unknown"),
    )


def child_exit(server, worker):
    # Called in the MASTER process after ANY worker dies — guaranteed to run
    server.log.error(
        "child_exit hook (master): pid=%s age=%s exitcode=%s",
        worker.pid,
        worker.age,
        getattr(worker, "exitcode", "unknown"),
    )
