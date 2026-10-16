# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Explicit, process-local flow tracing. No Holoscan 4.x Application hooks.

Carry a FlowTrace with each message (or associate it with a unique message ID
in application-owned state). Append on each visited operator, write at sinks.
Timestamps are monotonic nanoseconds; they measure host work, not GPU completion.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
import time


def now_ns():
    return time.monotonic_ns()


@dataclass(frozen=True)
class FlowTrace:
    message_id: int
    path: tuple = ()

    def __post_init__(self):
        if type(self.message_id) is not int or not 0 <= self.message_id < 2**64:
            raise ValueError("message_id must be an unsigned 64-bit integer")

    def append(self, operator, start_ns, end_ns=None):
        """Return a new branch, preserving the input trace for other consumers."""
        if end_ns is None:
            end_ns = now_ns()
        if not isinstance(operator, str) or not operator or any(ord(c) < 32 for c in operator):
            raise ValueError("operator must be a nonempty name without control characters")
        if (type(start_ns) is not int or type(end_ns) is not int
                or not 0 <= start_ns <= end_ns < 2**63):
            raise ValueError("timestamps must be ordered, nonnegative int64 nanoseconds")
        if self.path and start_ns < self.path[-1][2]:
            raise ValueError("operator starts before its predecessor ends")
        return FlowTrace(self.message_id, self.path + ((operator, start_ns, end_ns),))


class FlowLogger:
    """Thread-safe JSONL writer, opened exclusively to avoid mixing trials.

    Flush every record so live readers see it. Use as a context manager and
    close after the SDK RunSession has stopped and all callbacks have retired.
    """

    def __init__(self, filename=None):
        filename = filename or os.environ.get("HOLOSCAN_FLOW_TRACKING_LOG_FILE", "flow.jsonl")
        self._file = Path(filename).open("x", encoding="utf-8")
        self._lock = threading.Lock()

    def write(self, trace):
        if not trace.path:
            raise ValueError("cannot log an empty trace")
        record = {"version": 1, "clock": "monotonic", "unit": "ns",
                  "message_id": trace.message_id, "path": trace.path}
        with self._lock:
            self._file.write(json.dumps(record, separators=(",", ":")) + "\n")
            self._file.flush()

    def close(self):
        with self._lock:
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
