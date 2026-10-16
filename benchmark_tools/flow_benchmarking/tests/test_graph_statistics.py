# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app_perf_graph


class GraphStatisticsTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("pydot"), "install pydot for DOT tests")
    def test_dot_preserves_distinct_operators_with_port_like_names(self):
        import pydot
        stats = app_perf_graph.Statistics(count=1, total=2.0, maximum=2.0)
        nodes = {name: stats for name in ("camera:0", "camera:1", "node", "edge")}
        edges = {("camera:0", "node"): stats, ("camera:1", "edge"): stats}
        graph = app_perf_graph.create_graph(nodes, edges, 2)
        parsed = pydot.graph_from_dot_data(graph.to_string())[0]
        identifiers = [node.get_name() for node in parsed.get_nodes()]
        self.assertEqual(len(set(identifiers)), 4)
        self.assertTrue(all(identifier not in ("node", "edge", "graph")
                            and ":" not in identifier for identifier in identifiers))
        labels = {node.get_name(): json.loads(node.get_label()).splitlines()[0]
                  for node in parsed.get_nodes()}
        self.assertCountEqual(labels.values(), nodes)
        self.assertEqual({(labels[edge.get_source()], labels[edge.get_destination()])
                          for edge in parsed.get_edges()}, set(edges))

    @unittest.skipUnless(importlib.util.find_spec("pydot"), "install pydot for DOT tests")
    def test_dot_labels_preserve_quotes_and_literal_backslash_sequences(self):
        import pydot
        name = 'camera"\\N\\n'
        stats = app_perf_graph.Statistics(count=1, total=2.0, maximum=2.0)
        graph = app_perf_graph.create_graph({name: stats}, {}, 1)
        parsed = pydot.graph_from_dot_data(graph.to_string())[0]
        try:
            label = json.loads(parsed.get_nodes()[0].get_label())
        except json.JSONDecodeError as error:
            self.fail(f"operator name was not safely escaped in its DOT label: {error}")
        self.assertEqual(label.splitlines()[0], name)

    def test_batches_keep_one_observation_per_message_not_per_invocation(self):
        # A 10 ms invocation serves two messages; a 1 ms invocation serves one.
        # Their per-message mean is 7 ms, while the per-invocation mean is 5.5 ms.
        rows = [
            (1, [["source", 0, 1000000], ["batch", 10000000, 20000000],
                 ["sink", 21000000, 22000000]]),
            (2, [["source", 2000000, 3000000], ["batch", 10000000, 20000000],
                 ["sink", 21000000, 22000000]]),
            (3, [["source", 30000000, 31000000], ["batch", 40000000, 41000000],
                 ["sink", 44000000, 45000000]]),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow.jsonl"
            path.write_text("".join(json.dumps(dict(version=1, clock="monotonic", unit="ns",
                                                   message_id=i, path=hops)) + "\n"
                                    for i, hops in rows))
            nodes, edges, count = app_perf_graph.collect_statistics([path], 0, 0)
        self.assertEqual(count, 3)
        self.assertEqual(nodes["batch"].count, 3)
        self.assertEqual(nodes["batch"].mean, 7.0)
        self.assertEqual(nodes["sink"].count, 3)
        self.assertEqual(edges[("batch", "sink")].count, 3)
        self.assertAlmostEqual(edges[("batch", "sink")].mean, 5 / 3)

    def test_branches_use_local_counts_and_shared_prefix_only_once(self):
        self.assertTrue(hasattr(app_perf_graph, "collect_statistics"), "missing path-aware statistics")
        rows = [
            (1, [["s", 0, 1000000], ["left", 2000000, 4000000]]),
            (1, [["s", 0, 1000000], ["right", 3000000, 6000000]]),
            (2, [["s", 10000000, 13000000], ["left", 14000000, 20000000]]),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow.jsonl"
            path.write_text("".join(json.dumps(dict(version=1, clock="monotonic", unit="ns",
                                                   message_id=i, path=hops)) + "\n"
                                    for i, hops in rows))
            nodes, edges, count = app_perf_graph.collect_statistics([path], 0, 0)
        self.assertEqual(nodes["s"].count, 2)
        self.assertEqual(nodes["s"].mean, 2.0)
        self.assertEqual(nodes["left"].mean, 4.0)
        self.assertEqual(nodes["right"].mean, 3.0)
        self.assertEqual(edges[("s", "right")].mean, 2.0)
        self.assertEqual(count, 3)

    def test_live_partial_record_is_retried_and_warmup_is_per_path(self):
        self.assertTrue(hasattr(app_perf_graph, "collect_statistics"), "missing path-aware statistics")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow.log"
            path.write_text("(s,0,1000) -> (a,2000,3000)\n(s,4000,5000) -> (a,6000,8000)\n"
                            "(s,9000,10000) -> (b,11000,12000)\n(s,13000,14000) -> (a,15000,")
            nodes, _, count = app_perf_graph.collect_statistics([path], 1, 0, live=True)
            self.assertEqual(count, 1)
            self.assertEqual(nodes["a"].mean, 2.0)
            with path.open("a") as stream:
                stream.write("19000)\n")
            nodes, _, count = app_perf_graph.collect_statistics([path], 1, 0, live=True)
            self.assertEqual(count, 2)
            self.assertEqual(nodes["a"].mean, 3.0)


if __name__ == "__main__":
    unittest.main()
