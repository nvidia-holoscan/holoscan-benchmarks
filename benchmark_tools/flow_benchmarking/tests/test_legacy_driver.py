# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Historical report processing must not invoke the retired SDK 4 collector."""
from pathlib import Path
import subprocess
import unittest

DRIVER = Path(__file__).resolve().parents[3] / "benchmarks/release_benchmarking/run_benchmarks.sh"


class HistoricalDriverTests(unittest.TestCase):
    def test_collection_redirects_to_sdk5_before_touching_workloads(self):
        result = subprocess.run(["bash", str(DRIVER)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--run-command", result.stderr)
        self.assertIn("--process", result.stderr)
        self.assertNotIn("configuration filepath", result.stdout)

    def test_help_keeps_historical_processing_available(self):
        result = subprocess.run(["bash", str(DRIVER), "--help"], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--process", result.stdout)


if __name__ == "__main__":
    unittest.main()
