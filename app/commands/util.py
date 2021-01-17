import logging
import time

logger = logging.getLogger(__name__)

class Timer:
    def __init__(self, reason):
        self.reason = reason
        self.start, self.end = 0, 0

    def __enter__(self):
        self.start = time.perf_counter()

    def __exit__(self, result_type, value, traceback):
        self.end = time.perf_counter()
        logger.info("Finished: %s in %s s", self.reason, self.end - self.start)
