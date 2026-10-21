"""Cooperative checks plus an external process-tree watchdog."""

import multiprocessing as mp
import time
import traceback

import psutil

from . import errors


class Budget:
    def __init__(self, config, started=None, checkpoint=None):
        self.config = config
        self.started = time.perf_counter() if started is None else started
        self.deadline = self.started + config.time_limit_seconds
        self.process = psutil.Process()
        self.peak = 0
        self._checkpoint = checkpoint

    def evidence(self):
        mem = self.process.memory_info()
        self.peak = max(self.peak, mem.rss, getattr(mem, "peak_wset", 0))
        return {
            "elapsed_seconds": time.perf_counter() - self.started,
            "peak_process_mib": self.peak / 2**20,
        }

    def check(self):
        evidence = self.evidence()
        if self.peak > self.config.memory_limit_bytes:
            raise errors.ResourceLimitError(
                "memory_limit", "process-memory ceiling reached", evidence
            )
        if time.perf_counter() >= self.deadline:
            raise errors.ResourceLimitError("time_limit", "wall-clock budget exhausted", evidence)

    def preflight(self, additional_bytes):
        self.check()
        if self.process.memory_info().rss + additional_bytes > self.config.memory_limit_bytes:
            raise errors.ResourceLimitError(
                "memory_limit", "estimated working set exceeds ceiling", self.evidence()
            )

    def checkpoint(self, diagnostics):
        if self._checkpoint:
            self._checkpoint(dict(diagnostics, **self.evidence()))


def _entry(connection, function, args, config, started):
    try:
        budget = Budget(config, started, lambda d: connection.send(("progress", d)))
        budget.check()
        result = function(*args, budget=budget)
        budget.check()
        connection.send(("result", result))
    except errors.BridgeError as exc:
        connection.send(("expected", (type(exc).__name__, exc.status, exc.reason, exc.diagnostics)))
    except Exception as exc:  # noqa: BLE001 - transport unexpected defects with their traceback
        connection.send(("unexpected", (exc, traceback.format_exc())))
    finally:
        connection.close()


def _terminate(worker, known):
    try:
        known.extend(psutil.Process(worker.pid).children(recursive=True))
    except psutil.NoSuchProcess:
        pass
    for child in reversed(known):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    if worker.is_alive():
        worker.terminate()
    worker.join(timeout=1)
    if worker.is_alive():
        worker.kill()
        worker.join(timeout=1)


def run_guarded(function, args, config, started=None):
    started = time.perf_counter() if started is None else started
    context = mp.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    worker = context.Process(target=_entry, args=(sender, function, args, config, started))
    worker.start()
    sender.close()
    diagnostics = {}
    known = []
    peak = 0
    try:
        while True:
            elapsed = time.perf_counter() - started
            try:
                tree = [
                    psutil.Process(worker.pid),
                    *psutil.Process(worker.pid).children(recursive=True),
                ]
                known.extend(tree[1:])
                for member in tree:
                    try:
                        mem = member.memory_info()
                        peak = max(peak, mem.rss, getattr(mem, "peak_wset", 0))
                    except psutil.NoSuchProcess:
                        pass
            except psutil.NoSuchProcess:
                pass
            diagnostics.update(elapsed_seconds=elapsed, peak_process_mib=peak / 2**20)
            if peak > config.memory_limit_bytes:
                raise errors.ResourceLimitError(
                    "memory_limit", "worker process-memory ceiling reached", diagnostics
                )
            if elapsed >= config.time_limit_seconds:
                raise errors.ResourceLimitError(
                    "time_limit", "worker deadline reached", diagnostics
                )
            if receiver.poll(0.02):
                try:
                    kind, payload = receiver.recv()
                except EOFError:
                    raise RuntimeError(
                        f"bridge worker exited without a result: {worker.exitcode}"
                    ) from None
                if kind == "progress":
                    diagnostics.update(payload)
                elif kind == "expected":
                    name, status, reason, details = payload
                    raise getattr(errors, name)(status, reason, {**diagnostics, **details})
                elif kind == "unexpected":
                    exc, tb = payload
                    exc.add_note("Remote bridge worker traceback:\n" + tb)
                    raise exc
                else:
                    if time.perf_counter() - started >= config.time_limit_seconds:
                        raise errors.ResourceLimitError(
                            "time_limit", "result transfer exceeded deadline", diagnostics
                        )
                    if hasattr(payload, "_seal"):
                        payload._seal()
                    return payload
            elif not worker.is_alive():
                # One final pipe check handles the send/exit race.
                if not receiver.poll(0.05):
                    raise RuntimeError(f"bridge worker exited without a result: {worker.exitcode}")
    finally:
        _terminate(worker, known)
        receiver.close()
