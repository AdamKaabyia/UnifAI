import faulthandler
import logging
import os
import sys
import threading
import traceback


def on_starting(server):
    # Register a fork handler in the MASTER process.
    # Uses os.write() directly — signal-safe, no Python locks, no logging system.
    # This fires on EVERY os.fork() call regardless of which thread calls it.
    def _before_fork():
        pid = os.getpid()
        # Write directly to stderr fd=2, bypassing all Python logging locks
        msg = f"\nFORK-TRAP pid={pid} stack:\n{''.join(traceback.format_stack())}\n"
        os.write(2, msg.encode("utf-8", errors="replace"))

    os.register_at_fork(before=_before_fork)


def pre_fork(server, worker):
    # Called by Gunicorn arbiter just before it calls os.fork() for a worker.
    # Use both the gunicorn logger AND direct stderr write for reliability.
    msg = f"\nGUNICORN-PRE-FORK pid={os.getpid()} current_workers={list(server.WORKERS.keys())}\n"
    os.write(2, msg.encode("utf-8", errors="replace"))
    server.log.warning(
        "pre_fork: Gunicorn is about to spawn a new worker (current workers: %s)",
        list(server.WORKERS.keys()),
    )


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
    # Called in the MASTER process after ANY worker dies that is in WORKERS dict
    server.log.error(
        "child_exit hook (master): pid=%s age=%s exitcode=%s",
        worker.pid,
        worker.age,
        getattr(worker, "exitcode", "unknown"),
    )
