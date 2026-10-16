# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import log_parser


def record(message_id, path):
    return json.dumps(dict(version=1, clock="monotonic", unit="ns", message_id=message_id, path=path)) + "\n"


class RecordsTests(unittest.TestCase):
    def parse(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow.jsonl"
            path.write_text(content)
            return log_parser.parse_log_as_paths_latencies(path)

    def test_nanoseconds_and_distinct_messages(self):
        path = [["source", 1000000, 1100000], ["sink", 2000000, 3000000]]
        self.assertEqual(self.parse(record(1, path) + record(2, path)), {"source→ sink": [2.0, 2.0]})

    def test_operator_separator_does_not_merge_distinct_paths(self):
        paths = self.parse(
            record(1, [["source→ sink", 0, 1000000]])
            + record(2, [["source", 0, 1000000], ["sink", 1000000, 2000000]])
            + record(3, [[r"source\u2192 sink", 0, 3000000]])
        )
        self.assertEqual(len(paths), 3)
        self.assertEqual(sorted(paths.values()), [[1.0], [2.0], [3.0]])

    def test_nearby_legacy_sink_times_are_distinct(self):
        self.assertEqual(self.parse("(source,1000,1100) -> (sink,2000,3000)\n"
                                   "(source,1000,1100) -> (sink,2000,3020)\n"),
                         {"source→ sink": [2.0, 2.02]})

    def test_bad_record_has_filename_and_line_number(self):
        for value in ("{bad}\n", record(1, [["sink", 200, 100]]),
                      record(1, [["source", 100, 200], ["sink", 150, 300]])):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, r"flow.jsonl:2"):
                    self.parse("# header\n" + value)

    def test_blank_and_status_lines_and_whitespace(self):
        self.assertEqual(self.parse("\n[info] hello\n  (source,1000,2000)\n"), {"source": [1.0]})


if __name__ == "__main__":
    unittest.main()
