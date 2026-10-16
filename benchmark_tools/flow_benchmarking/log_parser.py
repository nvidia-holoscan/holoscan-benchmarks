# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Read versioned SDK 5 flow records and legacy SDK 1–4 timestamp logs."""

from dataclasses import dataclass
import json
import re


@dataclass(frozen=True)
class FlowRecord:
    message_id: int | None
    path: tuple  # (operator, start_ns, end_ns), in traversal order

    @property
    def latency_ms(self):
        return (self.path[-1][2] - self.path[0][1]) / 1_000_000

    @property
    def path_name(self):
        # Escape the delimiter and the escape character so different topologies
        # cannot collapse to one analysis group when a name contains an arrow.
        return "→ ".join(hop[0].replace("\\", "\\\\").replace("→", r"\u2192")
                         for hop in self.path)


def parse_line_from_log(line):
    """Legacy API: return operator names and microsecond timestamp strings."""
    result = []
    for operator in line.strip().split("->"):
        match = re.fullmatch(r"\s*\(([^,()]+),\s*(\d+),\s*(\d+)\)\s*", operator)
        if not match:
            raise ValueError("invalid legacy operator timestamp tuple")
        name, start, end = match.groups()
        result.append([name.strip(), start, end])
    return result


def get_path_latency(op_timestamps, path_separator="→ "):
    return (path_separator.join(op[0] for op in op_timestamps),
            (int(op_timestamps[-1][2]) - int(op_timestamps[0][1])) / 1000)


def is_same_path(line1, line2):
    """Only exact timestamp tuples are duplicates; nearby times are distinct."""
    if not line1.strip() or not line2.strip():
        return False
    return parse_line_from_log(line1) == parse_line_from_log(line2)


def parse_record(line):
    line = line.strip()
    if line.startswith("{"):
        data = json.loads(line)
        if data.get("version") != 1 or data.get("unit") != "ns" or data.get("clock") != "monotonic":
            raise ValueError("expected flow version=1, unit=ns, clock=monotonic")
        identity = data.get("message_id")
        if type(identity) is not int or not 0 <= identity < 2**64:
            raise ValueError("invalid message_id")
        raw_path = data.get("path")
        if not isinstance(raw_path, list) or not raw_path:
            raise ValueError("path must be a nonempty list")
        path = []
        for hop in raw_path:
            if not isinstance(hop, list) or len(hop) != 3:
                raise ValueError("expected [operator, start_ns, end_ns]")
            path.append(tuple(hop))
    elif line.startswith("("):
        identity = None
        path = [(name, int(start) * 1000, int(end) * 1000)
                for name, start, end in parse_line_from_log(line)]
    else:
        return None  # blank lines, comments, SDK status output
    previous_end = 0
    for name, start, end in path:
        if not isinstance(name, str) or not name or any(ord(c) < 32 for c in name):
            raise ValueError("invalid operator name")
        if type(start) is not int or type(end) is not int or not 0 <= start <= end < 2**63:
            raise ValueError("invalid operator timestamps")
        if identity is not None and start < previous_end:
            raise ValueError("operator starts before its predecessor ends")
        previous_end = end
    return FlowRecord(identity, tuple(path))


def iter_flow_records(log_file, *, live=False):
    """Yield records with useful errors; defer an incomplete final live line.

    New records retain every message, including identical timestamps with distinct
    IDs. Only consecutive exact legacy duplicates are suppressed for old SDK logs.
    """
    previous = None
    with open(log_file, encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if live and not line.endswith("\n"):
                break
            try:
                record = parse_record(line)
            except (ValueError, TypeError, KeyError) as error:
                raise ValueError(f"{log_file}:{number}: {error}") from error
            if record is None:
                continue
            if record.message_id is None and record == previous:
                continue
            previous = record
            yield record


def parse_log_as_paths_latencies(log_file):
    paths = {}
    for record in iter_flow_records(log_file):
        paths.setdefault(record.path_name, []).append(record.latency_ms)
    return paths
