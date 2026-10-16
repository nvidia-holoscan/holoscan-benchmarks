// SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include "flow_tracking.hpp"

#include <holoscan/core/sample.hpp>

#include <map>
#include <utility>

namespace holoscan_benchmark {

// One instance belongs to one process-local run. Each key identifies one
// message's source-to-sink provenance branch, not just the current operator.
// Copy a trace into each outgoing branch before publishing a fan-out message.
// At a join, take each contributing branch and append the same join interval.
// The bound limits outstanding entries, not allocation latency or path length.
class TraceRegistry {
 public:
  explicit TraceRegistry(std::size_t capacity) : capacity_(capacity) {
    if (!capacity) throw std::invalid_argument("trace capacity must be positive");
  }

  void put(std::string branch, FlowTrace trace) {
    if (branch.empty() || !trace.message_id()) {
      throw std::invalid_argument("SDK trace IDs and branch names must be nonempty");
    }
    const auto key = std::make_pair(trace.message_id(), std::move(branch));
    const std::lock_guard lock{mutex_};
    if (traces_.contains(key)) throw std::invalid_argument("trace branch already exists");
    if (traces_.size() == capacity_) throw std::length_error("trace capacity exceeded");
    traces_.emplace(key, std::move(trace));
  }

  FlowTrace take(std::uint64_t id, const std::string& branch) {
    const std::lock_guard lock{mutex_};
    const auto found = traces_.find({id, branch});
    if (found == traces_.end()) throw std::out_of_range("missing trace branch");
    auto result = std::move(found->second);
    traces_.erase(found);
    return result;
  }

  // Call only when the application knows this branch was dropped/cancelled and
  // cannot still arrive. SDK queue drops are not observed automatically. An
  // unknown drop must fail on capacity exhaustion rather than leak indefinitely.
  bool retire(std::uint64_t id, const std::string& branch) {
    const std::lock_guard lock{mutex_};
    return traces_.erase({id, branch}) != 0;
  }

  [[nodiscard]] std::size_t pending() const {
    const std::lock_guard lock{mutex_};
    return traces_.size();
  }

 private:
  const std::size_t capacity_;
  mutable std::mutex mutex_;
  std::map<std::pair<std::uint64_t, std::string>, FlowTrace> traces_;
};

// Use receive(), not receive_data(), to obtain the input SampleMetadata. Pass
// these options to emit() or emit_tensor() when publishing a newly allocated
// output; changing the payload does not require changing the input provenance.
// This forwards semantic metadata within the same RunSession clock scope. It
// does not copy runtime-owned publication timestamps or invent a capture time.
inline holoscan::EmitOptions forward_flow_metadata(const holoscan::SampleMetadata& metadata) {
  if (!metadata.trace_id) throw std::invalid_argument("sample has no trace ID");
  holoscan::EmitOptions options{
      .frame_id = metadata.frame_id,
      .trace = holoscan::TraceContext::root(metadata.trace_id),
      .flags = metadata.flags,
  };
  if (metadata.source_clock_id.valid()) options.capture_time = metadata.capture_time();
  return options;
}

}  // namespace holoscan_benchmark
