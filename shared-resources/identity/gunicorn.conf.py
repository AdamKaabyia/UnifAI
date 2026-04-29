import faulthandler
import logging
import sys

logger = logging.getLogger("gunicorn.error")


def post_fork(server, worker):
    faulthandler.enable(file=sys.stderr)


def worker_exit(server, worker):
    logger.error(
        "worker_exit hook: pid=%s exitcode=%s",
        worker.pid,
        getattr(worker, "exitcode", "unknown"),
    )
