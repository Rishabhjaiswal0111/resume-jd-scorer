"""Wall-clock timing of pipeline steps, stored with the work it measures.

    timings = Timings()
    with timings.step("evaluate_ms"):
        await evaluate(...)
    run.timings = timings.as_dict()   # {"evaluate_ms": 812, "total_ms": 845}

A step that raises is still recorded (up to the failure), so failed runs show where the
time went. Repeated steps add up.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


def elapsed_ms(start: float) -> int:
    """Milliseconds since a time.perf_counter() reading."""
    return round((time.perf_counter() - start) * 1000)


class Timings:
    def __init__(self) -> None:
        self.started = time.perf_counter()
        self._values: dict[str, Any] = {}

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self._values[name] = self._values.get(name, 0) + elapsed_ms(start)

    def note(self, name: str, value: Any) -> None:
        """A fact about the run that explains a time (e.g. jd_parse_cached=True)."""
        self._values[name] = value

    def total_ms(self) -> int:
        return elapsed_ms(self.started)

    def as_dict(self) -> dict[str, Any]:
        return {**self._values, "total_ms": self.total_ms()}
