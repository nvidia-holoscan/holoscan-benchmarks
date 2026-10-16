# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Render recorded operator intervals and inter-operator delays in milliseconds."""

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import time

from log_parser import iter_flow_records


@dataclass
class Statistics:
    count: int = 0
    total: float = 0.0
    maximum: float = float("-inf")

    def add(self, latency):
        self.count += 1
        self.total += latency
        self.maximum = max(self.maximum, latency)

    @property
    def mean(self):
        return self.total / self.count


def collect_statistics(filenames, skip_begin=10, discard_last=10, *, live=False):
    """Trim per file/path; count shared branch prefixes once per message.

    Node samples are unique (message ID, hop) observations within each file;
    edges use the message ID and adjacent hops. A shared invocation in a batch
    or join contributes once for each source message. Means and counts therefore
    describe message observations, not unique operator invocations.

    Live snapshots are recomputed so warmup, partially written lines, and file
    replacement behave exactly like offline analysis. Large logs cost more to
    refresh; this intentionally avoids the former lossy offset/tail bookkeeping.
    """
    if skip_begin < 0 or discard_last < 0:
        raise ValueError("sample exclusions must be nonnegative")
    nodes, edges = defaultdict(Statistics), defaultdict(Statistics)
    count = 0
    for filename in filenames:
        paths = defaultdict(list)
        for record in iter_flow_records(filename, live=live):
            paths[record.path_name].append(record)
        seen_nodes, seen_edges = set(), set()
        for records in paths.values():
            stop = len(records) - discard_last if discard_last else len(records)
            for record in records[skip_begin:max(skip_begin, stop)]:
                count += 1
                for index, hop in enumerate(record.path):
                    name, start, end = hop
                    key = (record.message_id, hop)
                    if key not in seen_nodes:
                        nodes[name].add((end - start) / 1_000_000)
                        seen_nodes.add(key)
                    if index:
                        previous = record.path[index - 1]
                        key = (record.message_id, previous, hop)
                        if key not in seen_edges:
                            edges[(previous[0], name)].add((start - previous[2]) / 1_000_000)
                            seen_edges.add(key)
    return dict(nodes), dict(edges), count


def create_graph(nodes, edges, count, highlight=False):
    import pydot
    graph = pydot.Dot(graph_type="digraph", rankdir="TB")
    graph.set_label(f"Host flow timings (ms) — {count} completed path records\\n"
                    "Averages and n use message observations, not operator invocations")
    average = sum(item.mean for item in nodes.values()) / len(nodes) if nodes else 0
    node_ids = {name: f"operator_{index}" for index, name in enumerate(nodes)}
    for name, stats in nodes.items():
        # DOT interprets colons as ports and reserves names such as node/edge.
        # Keep names in labels only, escaping literal backslashes and quotes.
        label = json.dumps(f"{name}\navg: {stats.mean:.3f}\nmax: {stats.maximum:.3f}\nn: {stats.count}",
                           ensure_ascii=False)
        graph.add_node(pydot.Node(
            node_ids[name], label=label,
            color="red" if highlight and stats.mean > average else "black"))
    for (source, target), stats in edges.items():
        graph.add_edge(pydot.Edge(node_ids[source], node_ids[target],
                                 label=f"avg: {stats.mean:.3f}\\nmax: {stats.maximum:.3f}\\nn: {stats.count}"))
    return graph


def nonnegative_int(value):
    result = int(value)
    if result < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filenames", nargs="+", type=Path)
    parser.add_argument("-l", "--live", action="store_true", help="watch one directory")
    parser.add_argument("-o", "--output", type=Path, default=Path("application_perf.dot"))
    parser.add_argument("--highlight", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--skip-begin", type=nonnegative_int, default=10)
    parser.add_argument("--discard-last", type=nonnegative_int, default=10)
    args = parser.parse_args()
    if args.live and (len(args.filenames) != 1 or not args.filenames[0].is_dir()):
        parser.error("live mode requires one directory")
    while True:
        filenames = (sorted(p for p in args.filenames[0].iterdir()
                            if p.suffix in (".jsonl", ".log") and p.is_file()
                            and not p.name.startswith(("console_", "benchmark")))
                     if args.live else args.filenames)
        nodes, edges, count = collect_statistics(filenames, args.skip_begin, args.discard_last,
                                                live=args.live)
        if count:
            graph = create_graph(nodes, edges, count, args.highlight)
            temporary = args.output.with_suffix(args.output.suffix + ".tmp")
            graph.write_raw(str(temporary))
            temporary.replace(args.output)
            if args.verbose:
                print(f"Wrote {count} path records to {args.output}", flush=True)
        elif not args.live:
            parser.error("no flow samples remain; lower --skip-begin/--discard-last")
        if not args.live:
            return
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
