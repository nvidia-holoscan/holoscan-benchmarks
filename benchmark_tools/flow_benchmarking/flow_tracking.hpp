// SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iomanip>
#include <locale>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace holoscan_benchmark {

inline std::int64_t now_ns() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
             std::chrono::steady_clock::now().time_since_epoch()).count();
}

struct Hop {
  std::string name;
  std::int64_t start_ns;
  std::int64_t end_ns;
};

// Application-owned process-local metadata. Copy a trace at fan-out, append
// each operator's interval, and write each completed path at its sink.
// This is not a registered Holoscan port payload or a real-time-safe allocator.
class FlowTrace {
 public:
  explicit FlowTrace(std::uint64_t message_id) : message_id_(message_id) {}

  void append(std::string_view name, std::int64_t start, std::int64_t end = now_ns()) {
    if (name.empty() || name.find_first_of(std::string_view{"\0\n\r\t", 4}) != name.npos) {
      throw std::invalid_argument("operator name is empty or contains control characters");
    }
    for (unsigned char c : name) {
      if (c < 32) throw std::invalid_argument("operator name contains control characters");
    }
    if (start < 0 || end < start || (!path_.empty() && start < path_.back().end_ns)) {
      throw std::invalid_argument("timestamps must be ordered monotonic nanoseconds");
    }
    path_.push_back({std::string{name}, start, end});
  }

  [[nodiscard]] std::uint64_t message_id() const { return message_id_; }
  [[nodiscard]] const std::vector<Hop>& path() const { return path_; }

 private:
  std::uint64_t message_id_;
  std::vector<Hop> path_;
};

class FlowLogger {
 public:
  static std::string default_filename() {
    const char* value = std::getenv("HOLOSCAN_FLOW_TRACKING_LOG_FILE");
    return value && *value ? value : "flow.jsonl";
  }

  explicit FlowLogger(const std::string& filename = default_filename()) {
    file_ = std::fopen(filename.c_str(), "wx");
    if (!file_) throw std::runtime_error("cannot create new flow log: " + filename);
  }
  FlowLogger(const FlowLogger&) = delete;
  FlowLogger& operator=(const FlowLogger&) = delete;
  ~FlowLogger() { if (file_) std::fclose(file_); }

  void write(const FlowTrace& trace) {
    if (trace.path().empty()) throw std::invalid_argument("cannot log an empty trace");
    std::ostringstream stream;
    stream.imbue(std::locale::classic());
    stream << "{\"version\":1,\"clock\":\"monotonic\",\"unit\":\"ns\",\"message_id\":"
           << trace.message_id() << ",\"path\":[";
    bool first = true;
    for (const auto& hop : trace.path()) {
      stream << (first ? "" : ",") << '[' << std::quoted(hop.name) << ','
             << hop.start_ns << ',' << hop.end_ns << ']';
      first = false;
    }
    stream << "]}\n";
    const auto record = stream.str();
    const std::lock_guard lock{mutex_};
    if (!file_) throw std::runtime_error("flow log is closed");
    if (std::fwrite(record.data(), 1, record.size(), file_) != record.size() ||
        std::fflush(file_) != 0) {
      throw std::runtime_error("failed to write flow log");
    }
  }

  // Call after RunSession.wait(), once every callback has retired.
  void close() {
    const std::lock_guard lock{mutex_};
    if (!file_) return;
    auto* file = file_;
    file_ = nullptr;
    if (std::fclose(file) != 0) throw std::runtime_error("failed to close flow log");
  }

 private:
  std::FILE* file_{};
  std::mutex mutex_;
};

}  // namespace holoscan_benchmark
