# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import csv
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("matplotlib"),
                     "install flow_benchmarking/requirements.txt for analysis tests")
class AnalysisTests(unittest.TestCase):
    def run_analysis(self, directory, *arguments):
        return subprocess.run(
            [sys.executable, str(TOOLS / "analyze.py"), "--skip-begin", "0",
             "--discard-last", "0", *map(str, arguments)],
            cwd=directory, capture_output=True, text=True)

    def test_duplicate_explicit_group_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            flow = Path(directory) / "flow.log"
            flow.write_text("(source,1000,2000) -> (sink,3000,4000)\n")
            utilization = Path(directory) / "utilization.csv"
            utilization.write_text("20,40,\n")
            for flag, path in (("-g", flow), ("-u", utilization)):
                with self.subTest(flag=flag):
                    arguments = [flag, path, "trial", flag, path, "trial", "--avg"]
                    if flag == "-u":
                        arguments.extend(["-g", flow])
                    result = self.run_analysis(directory, *arguments)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("duplicate group name", result.stderr.lower())
                    self.assertIn("trial", result.stderr)

    def test_automatic_log_group_names_reserve_explicit_names_in_any_order(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.log"
            first.write_text("(source,1000,2000) -> (sink,3000,4000)\n")
            second = Path(directory) / "second.log"
            second.write_text("(source,5000,6000) -> (sink,7000,9000)\n")
            output = Path(directory) / "summary.csv"
            cases = [
                (["-g", first, "-g", second, "Group1"], ["Group2", "Group1"]),
                (["-g", first, "Group1", "-g", second], ["Group1", "Group2"]),
            ]
            for arguments, expected_names in cases:
                with self.subTest(expected_names=expected_names):
                    result = self.run_analysis(directory, *arguments, "--output-csv", output,
                                               "--avg", "--save-csv")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    with output.open() as stream:
                        rows = list(csv.DictReader(stream))
                    self.assertEqual([row["group"] for row in rows], expected_names)
                    self.assertEqual([float(row["avg_ms"]) for row in rows], [3.0, 4.0])
                    self.assertEqual((Path(directory) / "avg_values.csv").read_text(), "3.0,4.0,")

    def test_automatic_utilization_group_names_reserve_explicit_names_in_any_order(self):
        with tempfile.TemporaryDirectory() as directory:
            flow = Path(directory) / "flow.log"
            flow.write_text("(source,1000,2000) -> (sink,3000,4000)\n")
            first = Path(directory) / "first.csv"
            first.write_text("20,40,\n")
            second = Path(directory) / "second.csv"
            second.write_text("60,80,\n")
            cases = [
                (["-u", first, "-u", second, "UGroup1"], ["UGroup2", "UGroup1"]),
                (["-u", first, "UGroup1", "-u", second], ["UGroup1", "UGroup2"]),
            ]
            for arguments, expected_names in cases:
                with self.subTest(expected_names=expected_names):
                    result = self.run_analysis(directory, "-g", flow, *arguments, "--save-csv")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    for name in expected_names:
                        self.assertIn(name, result.stdout)
                    self.assertEqual(
                        (Path(directory) / "avg_gpu_utilization_values.csv").read_text(),
                        "30.0,70.0,")

    def test_cdf_paths_support_operators_with_the_same_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "branches.log"
            path.write_text("(source,1000,2000) -> (sink0,3000,4000)\n"
                            "(source,5000,6000) -> (sink1,7000,9000)\n")
            output = Path(directory) / "cdf.svg"
            result = self.run_analysis(directory, "-g", path, "trial", "--draw-cdf-paths",
                                       output, "--no-display-graphs")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            svg = output.read_text()
            self.assertIn("sink0", svg)
            self.assertIn("sink1", svg)

    def test_export_contains_all_paths_and_explicit_sample_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow.log"
            path.write_text("(s,1000,2000) -> (a,3000,4000)\n"
                            "(s,5000,6000) -> (b,7000,9000)\n")
            output = Path(directory) / "summary.csv"
            result = subprocess.run([sys.executable, str(TOOLS / "analyze.py"), "-g", str(path),
                                     "trial", "--skip-begin", "0", "--discard-last", "0",
                                     "--output-csv", str(output), "--avg"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with output.open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["path"] for row in rows], ["s→ a", "s→ b"])
            self.assertEqual([row["count"] for row in rows], ["1", "1"])
            self.assertEqual([float(row["avg_ms"]) for row in rows], [3.0, 4.0])

    def test_no_samples_returns_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.log"
            path.touch()
            result = subprocess.run([sys.executable, str(TOOLS / "analyze.py"), "-g", str(path), "--avg"],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no flow samples", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
