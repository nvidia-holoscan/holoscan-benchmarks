# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Optional SDK integration checks; ordinary CPU CI skips these when SDK paths are absent.

Set HOLOSCAN_SDK_PREFIX to compile the public metadata/correlation helper test.
Set HOLOSCAN_TENSOR_FLOW_EXECUTABLE to exercise the built Tensor Graph example.
"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parents[1]
SDK_PREFIX = os.environ.get("HOLOSCAN_SDK_PREFIX")
TENSOR_EXECUTABLE = os.environ.get("HOLOSCAN_TENSOR_FLOW_EXECUTABLE")


@unittest.skipUnless(SDK_PREFIX, "set HOLOSCAN_SDK_PREFIX for SDK helper integration")
class SdkCorrelationTests(unittest.TestCase):
    def test_branches_capacity_drop_retirement_and_metadata_forwarding(self):
        # This catches destructive fan-out lookup, overwritten provenance, unbounded
        # pending state, and lost metadata when publishing newly allocated tensors.
        source = r'''
#include "sdk_flow_tracking.hpp"
#include <cassert>
#include <stdexcept>
using namespace holoscan_benchmark;
template <typename Error, typename Fn> void rejects(Fn fn) {
  bool failed = false;
  try { fn(); } catch (const Error&) { failed = true; }
  assert(failed);
}
int main() {
  TraceRegistry registry{2};
  FlowTrace root{7};
  root.append("source", 10, 20);
  registry.put("left", root);
  registry.put("right", root);
  rejects<std::invalid_argument>([&] { registry.put("left", root); });
  rejects<std::length_error>([&] { registry.put("overflow", FlowTrace{8}); });
  auto left = registry.take(7, "left");
  left.append("left", 30, 40);
  registry.put("left", std::move(left));
  auto right = registry.take(7, "right");
  assert(right.path().size() == 1 && right.message_id() == 7);
  registry.put("right", std::move(right));
  assert(registry.retire(7, "right"));
  assert(!registry.retire(7, "right"));
  assert(registry.pending() == 1);
  assert(registry.take(7, "left").path().size() == 2);
  assert(registry.pending() == 0);
  rejects<std::out_of_range>([&] { registry.take(7, "left"); });
  rejects<std::invalid_argument>([&] { registry.put("left", FlowTrace{0}); });

  holoscan::SampleMetadata metadata;
  metadata.trace_id = 7;
  metadata.frame_id = 101;
  metadata.capture_timestamp_ns = 0;  // valid zero must survive forwarding
  metadata.source_clock_id = holoscan::ClockId{2};
  metadata.flags = holoscan::SampleFlags::kDegraded;
  const auto forwarded = forward_flow_metadata(metadata);
  assert(forwarded.trace && forwarded.trace->trace_id == 7);
  assert(forwarded.frame_id && *forwarded.frame_id == 101);
  assert(forwarded.capture_time && forwarded.capture_time->timestamp_ns == 0);
  assert(forwarded.capture_time->clock_id == holoscan::ClockId{2});
  assert(forwarded.flags == holoscan::SampleFlags::kDegraded);
  metadata.source_clock_id = {};
  assert(!forward_flow_metadata(metadata).capture_time);
  metadata.trace_id = 0;
  rejects<std::invalid_argument>([&] { forward_flow_metadata(metadata); });
}
'''
        with tempfile.TemporaryDirectory(prefix="sdk-flow-helper-") as directory:
            root = Path(directory)
            (root / "test.cpp").write_text(source)
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 4.0)\n"
                "project(flow_helper_test LANGUAGES CXX)\n"
                "find_package(holoscan 5.0 REQUIRED CONFIG COMPONENTS core)\n"
                "find_package(Threads REQUIRED)\n"
                "add_executable(test_helper test.cpp)\n"
                "target_compile_features(test_helper PRIVATE cxx_std_20)\n"
                f'target_include_directories(test_helper PRIVATE "{TOOLS}")\n'
                "target_link_libraries(test_helper PRIVATE holoscan::core Threads::Threads)\n"
            )
            for command in (
                ["cmake", "-S", str(root), "-B", str(root / "build"),
                 f"-DCMAKE_PREFIX_PATH={SDK_PREFIX}"],
                ["cmake", "--build", str(root / "build"), "-j2"],
                [str(root / "build/test_helper")],
            ):
                result = subprocess.run(command, capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(TENSOR_EXECUTABLE, "set HOLOSCAN_TENSOR_FLOW_EXECUTABLE for Tensor Graph integration")
class TensorGraphTests(unittest.TestCase):
    def run_graph(self, *args):
        temporary = tempfile.TemporaryDirectory(prefix="tensor-flow-test-")
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "flow.jsonl"
        env = dict(os.environ, HOLOSCAN_NUM_SOURCE_MESSAGES="31",
                   HOLOSCAN_FLOW_TRACKING_LOG_FILE=str(path))
        result = subprocess.run([TENSOR_EXECUTABLE, *args], env=env, capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(summary["completed_frames"], 31)
        self.assertEqual(summary["pending_traces"], 0)
        self.assertGreater(summary["wall_seconds"], 0)
        return path, summary

    def test_tensor_metadata_survives_fanout_transform_and_aligned_join(self):
        path, summary = self.run_graph()
        records = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(records), 62)
        self.assertEqual(summary["path_records"], 62)
        self.assertEqual(summary["tracking"], True)
        for branch in ("left", "right"):
            branch_records = [record for record in records if record["path"][1][0] == branch]
            self.assertEqual([r["message_id"] for r in branch_records], list(range(1, 32)))
            for record in branch_records:
                self.assertEqual([hop[0] for hop in record["path"]], ["source", branch, "join"])
                self.assertTrue(all(0 <= hop[1] <= hop[2] for hop in record["path"]))
                self.assertTrue(all(a[2] <= b[1]
                                    for a, b in zip(record["path"], record["path"][1:])))
        for left, right in zip(records[::2], records[1::2]):
            self.assertEqual(left["path"][0], right["path"][0])
            self.assertEqual(left["path"][-1], right["path"][-1])

    def test_untracked_baseline_runs_same_graph_without_a_log(self):
        path, summary = self.run_graph("--no-tracking")
        self.assertFalse(path.exists())
        self.assertEqual(summary["tracking"], False)
        self.assertEqual(summary["path_records"], 0)

    def test_concurrent_instances_keep_independent_sdk_services_and_logs(self):
        # The installed SDK derives Tensor transport service names from graph
        # identity; identical graph names previously exhausted shared services.
        with tempfile.TemporaryDirectory(prefix="tensor-concurrent-") as directory:
            paths = [Path(directory) / f"flow-{i}.jsonl" for i in range(4)]
            processes = []
            try:
                for path in paths:
                    env = dict(os.environ, HOLOSCAN_NUM_SOURCE_MESSAGES="500",
                               HOLOSCAN_FLOW_TRACKING_LOG_FILE=str(path))
                    processes.append(subprocess.Popen([TENSOR_EXECUTABLE], env=env,
                                                      stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE, text=True))
                results = [process.communicate(timeout=30) for process in processes]
                for process, path, (stdout, stderr) in zip(processes, paths, results):
                    self.assertEqual(process.returncode, 0, stdout + stderr)
                    records = [json.loads(line) for line in path.read_text().splitlines()]
                    self.assertEqual(len(records), 1000)
                    for branch in ("left", "right"):
                        self.assertEqual([r["message_id"] for r in records
                                          if r["path"][1][0] == branch], list(range(1, 501)))
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.communicate()


if __name__ == "__main__":
    unittest.main()
