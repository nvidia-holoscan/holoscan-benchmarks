# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CPU-only regression coverage for Holoscan flow-log parsing."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import log_parser


class LogParserTests(unittest.TestCase):
    def test_operator_order_and_latency_in_milliseconds(self):
        parsed = log_parser.parse_line_from_log(
            " (source,1000000,1000500) -> (middle,1001000,1002000) "
            "-> (sink,1002500,1004000)\n"
        )
        self.assertEqual(
            parsed,
            [
                ["source", "1000000", "1000500"],
                ["middle", "1001000", "1002000"],
                ["sink", "1002500", "1004000"],
            ],
        )
        self.assertEqual(
            log_parser.get_path_latency(parsed, path_separator="/"),
            ("source/middle/sink", 4.0),
        )

    def test_duplicate_sink_timestamp_tolerance(self):
        original = "(source,1000,1100) -> (sink,2000,3000)"
        for timestamp, expected in ((2980, True), (3020, True), (2979, False), (3021, False)):
            with self.subTest(timestamp=timestamp):
                other = f"(source,1000,1100) -> (sink,2000,{timestamp})"
                self.assertEqual(log_parser.is_same_path(original, other), expected)

    def test_different_messages_and_paths_are_not_duplicates(self):
        original = "(source,1000,1100) -> (sink,2000,3000)"
        for other in (
            "",
            "(source,1001,1100) -> (sink,2000,3000)",
            "(source,1000,1101) -> (sink,2000,3000)",
            "(source,1000,1100) -> (other_sink,2000,3000)",
        ):
            with self.subTest(other=other):
                self.assertFalse(log_parser.is_same_path(original, other))

    def test_log_groups_paths_and_skips_consecutive_duplicates_and_status_lines(self):
        contents = (
            "[info] Starting application\n\n"
            "(source,1000,1100) -> (sink,2000,3000)\n"
            "(source,1000,1100) -> (sink,2000,3000)\n"
            "(source,1000,1100) -> (sink,2000,3020)\n"
            "[info] Still running\n"
            "(source,4000,4100) -> (sink,5000,7000)\n"
            "(source,8000,8100) -> (other_sink,9000,12000)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow.log"
            path.write_text(contents, encoding="utf-8")
            self.assertEqual(
                log_parser.parse_log_as_paths_latencies(path),
                {"source→ sink": [2.0, 3.0], "source→ other_sink": [4.0]},
            )

    def test_empty_log(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.log"
            path.touch()
            self.assertEqual(log_parser.parse_log_as_paths_latencies(path), {})


if __name__ == "__main__":
    unittest.main()
