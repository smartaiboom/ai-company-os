"""Local test server lifecycle; never enables an AI transport.

A wait deadline bounds observation, not the underlying request. On unknown,
retain this server and its non-daemon workers in the owning process; do not
exit, kill workers, rewrite reservations, or resend. An uninterruptible worker
can therefore keep the process alive. Transport cancellation needs a separate
cooperative design; increasing client timeouts cannot provide it.
"""
import threading
import time
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer


class ObservedServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = False  # Explicit bounded joins below, never implicit hang.

    def __init__(self, handler):
        self.events = []
        self.workers = []
        self.guard = threading.Lock()
        self.started = time.monotonic()
        super().__init__(("127.0.0.1", 0), handler)
        self.loop = threading.Thread(target=self.serve_forever,
                                     kwargs={"poll_interval": 0.01}, daemon=False)
        self.loop.start()

    def record(self, phase):
        # Fixed vocabulary: no exception text, input, headers, or response body.
        if phase not in {"request_started", "request_finished", "transport_started",
                         "transport_finished", "client_timeout", "shutdown_started",
                         "server_closed", "workers_finished", "completion_unknown"}:
            raise ValueError("Unsupported observation phase")
        with self.guard:
            self.events.append({"phase": phase,
                                "at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
                                "elapsed": time.monotonic() - self.started})

    def process_request(self, request, client_address):
        worker = threading.Thread(target=self.process_request_thread,
                                  args=(request, client_address), daemon=False)
        with self.guard:
            self.workers.append(worker)
            worker.start()

    def process_request_thread(self, request, client_address):
        self.record("request_started")
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.record("request_finished")

    def handle_error(self, request, client_address):
        pass  # Never print request/exception contents in a mock lifecycle runner.

    def requests_finished(self):
        """Evidence only after server shutdown and every tracked request exits."""
        with self.guard:
            return (not self.loop.is_alive() and self.socket.fileno() == -1
                    and all(not worker.is_alive() for worker in self.workers))

    def stop_and_observe(self, wait_seconds):
        """Stop accepting; report unknown on deadline, leave live workers intact.

        Call again after a cooperative worker completes to observe final state.
        shutdown itself waits for the short serve_forever poll, not this budget.
        """
        if wait_seconds < 0:
            raise ValueError("Negative wait budget")
        self.record("shutdown_started")
        self.shutdown()
        self.server_close()
        self.loop.join()
        self.record("server_closed")
        deadline = time.monotonic() + wait_seconds
        with self.guard:
            workers = list(self.workers)
        for worker in workers:
            worker.join(max(0, deadline - time.monotonic()))
        complete = all(not worker.is_alive() for worker in workers)
        self.record("workers_finished" if complete else "completion_unknown")
        return complete
