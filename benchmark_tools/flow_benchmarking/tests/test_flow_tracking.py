# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Exercise trace propagation, file lifetime, and the runner with real child processes."""
import importlib.util
import json
import os
import shutil
import signal
import time
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))


class TrackingTests(unittest.TestCase):
    def test_branch_copies_and_writer_flush(self):
        self.assertIsNotNone(importlib.util.find_spec("flow_tracking"), "flow tracker is missing")
        from flow_tracking import FlowLogger, FlowTrace
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flow.jsonl"
            root = FlowTrace(7).append("source", 1000, 2000)
            with FlowLogger(path) as logger:
                logger.write(root.append("left", 3000, 4000))
                logger.write(root.append("right", 4000, 6000))
                self.assertEqual(len(path.read_text().splitlines()), 2)
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(records[0]["path"], [["source", 1000, 2000], ["left", 3000, 4000]])
            self.assertEqual(records[1]["path"], [["source", 1000, 2000], ["right", 4000, 6000]])
            with self.assertRaises(ValueError):
                logger.write(root)
            with self.assertRaises(ValueError):
                root.append("invalid", 1000, 900)


class RunnerTests(unittest.TestCase):
    def run_fixture(self, body, *extra):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        fixture = directory / "app.py"
        fixture.write_text(body)
        result = subprocess.run(
            [sys.executable, str(TOOLS / "benchmark.py"), "--run-command",
             shlex.join([sys.executable, str(fixture)]), "-d", str(directory / "results"),
             *extra], capture_output=True, text=True, timeout=20,
        )
        return result, directory / "results"

    def test_runs_without_sdk_metadata_or_gpu_packages(self):
        result, output = self.run_fixture(
            'import os\nfrom pathlib import Path\n'
            'assert os.environ["HOLOSCAN_NUM_SOURCE_MESSAGES"] == "3"\n'
            'Path(os.environ["HOLOSCAN_FLOW_TRACKING_LOG_FILE"]).write_text('
            '"(source,1000,2000) -> (sink,3000,4000)\\n")\n',
            "-r", "2", "-i", "2", "-m", "3",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(output.glob("flow_*.jsonl"))), 4)

    def test_failed_child_does_not_report_success_even_with_log(self):
        result, _ = self.run_fixture(
            'import os\nfrom pathlib import Path\n'
            'Path(os.environ["HOLOSCAN_FLOW_TRACKING_LOG_FILE"]).write_text('
            '"(source,1000,2000) -> (sink,3000,4000)\\n")\nraise SystemExit(7)\n'
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exited with code 7", result.stderr)

    def test_timeout_kills_child(self):
        result, _ = self.run_fixture("import time\ntime.sleep(30)\n", "--timeout", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timed out", result.stderr)

    def assert_process_stopped(self, pid):
        try:
            state = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1][0]
        except FileNotFoundError:
            return
        if state != "Z":
            os.kill(pid, signal.SIGKILL)  # clean the reproduction even when the assertion fails
            self.fail(f"child {pid} survived runner cleanup")

    def test_failed_launcher_cleans_up_surviving_descendants(self):
        result, output = self.run_fixture(
            'import subprocess, sys\nfrom pathlib import Path\n'
            'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])\n'
            'Path(__file__).with_suffix(".pid").write_text(str(child.pid))\n'
            'raise SystemExit(7)\n', "--timeout", "5")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exited with code 7", result.stderr)
        self.assert_process_stopped(int((output.parent / "app.pid").read_text()))

    def test_successful_launcher_cannot_leave_background_work_running(self):
        result, output = self.run_fixture(
            'import os, subprocess, sys\nfrom pathlib import Path\n'
            'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])\n'
            'Path(__file__).with_suffix(".pid").write_text(str(child.pid))\n'
            'Path(os.environ["HOLOSCAN_FLOW_TRACKING_LOG_FILE"]).write_text('
            '"(source,1000,2000) -> (sink,3000,4000)\\n")\n', "--timeout", "5")
        # Always clean the reproduction, including when a broken runner returns 0.
        self.assert_process_stopped(int((output.parent / "app.pid").read_text()))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("background processes", result.stderr)

    def test_timeout_kills_descendant_ignoring_sigterm(self):
        result, output = self.run_fixture(
            'import os, signal, time\nfrom pathlib import Path\n'
            'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
            'Path(__file__).with_suffix(".pid").write_text(str(os.getpid()))\n'
            'time.sleep(30)\n', "--timeout", "1")
        self.assertNotEqual(result.returncode, 0)
        pid = int((output.parent / "app.pid").read_text())
        self.assert_process_stopped(pid)

    def test_interrupt_cancels_children_promptly(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            fixture = directory / "app.py"
            fixture.write_text('import os, time\nfrom pathlib import Path\n'
                               'Path(__file__).with_suffix(".pid").write_text(str(os.getpid()))\n'
                               'time.sleep(30)\n')
            process = subprocess.Popen(
                [sys.executable, str(TOOLS / "benchmark.py"), "--run-command",
                 shlex.join([sys.executable, str(fixture)]), "-d", str(directory / "results")],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            pidfile = directory / "app.pid"
            try:
                deadline = time.monotonic() + 5
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(pidfile.exists())
                process.send_signal(signal.SIGINT)
                _, stderr = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 130, stderr)
                self.assert_process_stopped(int(pidfile.read_text()))
            finally:
                if process.poll() is None:
                    if pidfile.exists():
                        os.kill(int(pidfile.read_text()), signal.SIGKILL)
                    process.kill()
                    process.communicate()

    def test_missing_or_empty_log_is_failure(self):
        for body in ("pass\n", 'import os\nfrom pathlib import Path\n'
                     'Path(os.environ["HOLOSCAN_FLOW_TRACKING_LOG_FILE"]).touch()\n'):
            with self.subTest(body=body):
                result, _ = self.run_fixture(body)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue("no flow records" in result.stderr or "No such file" in result.stderr, result.stderr)


class CppTrackingTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "C++ compiler unavailable")
    def test_cpp_writer_round_trips_through_python_parser(self):
        from log_parser import parse_log_as_paths_latencies
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "test"
            subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread",
                            "-I", str(TOOLS), str(TOOLS / "tests/flow_tracking_test.cpp"),
                            "-o", str(executable)], check=True, capture_output=True)
            output = root / "cpp.jsonl"
            subprocess.run([str(executable), str(output)], check=True, capture_output=True)
            self.assertEqual(parse_log_as_paths_latencies(output),
                             {"source→ left": [3.0], "source→ right": [5.0]})


if __name__ == "__main__":
    unittest.main()
