// SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
// SDK 5 graph: source -> work -> sink. Scalar message IDs correlate host traces
// in application-owned state; no SDK internals or automatic source patching.
#include "flow_tracking.hpp"

#include <holoscan/core/compile.hpp>
#include <holoscan/core/execution_context.hpp>
#include <holoscan/core/graph.hpp>
#include <holoscan/core/operator.hpp>
#include <holoscan/core/operator_spec.hpp>
#include <holoscan/core/run.hpp>
#include <holoscan/core/temporal_contract.hpp>
#include <holoscan/time/realtime_clock.hpp>

#include <condition_variable>
#include <iostream>
#include <map>
#include <memory>
#include <thread>

namespace {
using namespace std::chrono_literals;
using holoscan_benchmark::FlowTrace;
using holoscan_benchmark::now_ns;

// Owned by main for one run. IDs are unique across sources in this example.
// Real applications should scope this state to their run and retire traces for
// dropped messages. For branching, keep a separate copy for each outgoing path.
struct Observation {
  std::mutex mutex;
  std::condition_variable ready;
  std::map<std::uint64_t, FlowTrace> traces;
  std::unique_ptr<holoscan_benchmark::FlowLogger> logger;
  std::uint64_t limit{100};
  std::uint64_t received{};

  void put(FlowTrace trace) {
    const std::lock_guard lock{mutex};
    traces.insert_or_assign(trace.message_id(), std::move(trace));
  }
  FlowTrace take(std::uint64_t id) {
    const std::lock_guard lock{mutex};
    auto trace = traces.at(id);
    traces.erase(id);
    return trace;
  }
} observation;

class Source : public holoscan::Operator<> {
 public:
  holoscan::Output<std::uint64_t> out;
  void setup(holoscan::OperatorSpec& spec) override { spec.output(out, "out"); }
  holoscan::Contract contract() const override {
    holoscan::Contract result;
    result.trigger(holoscan::OnClock{.period = 1ms});
    return result;
  }
  holoscan::expected<void, holoscan::Error> compute(holoscan::ExecutionContext&) override {
    if (next_ == observation.limit) return {};
    const auto start = now_ns();
    FlowTrace trace{next_};
    trace.append("source", start);
    observation.put(std::move(trace));  // publish correlation before the message
    auto emitted = out.emit(next_);
    if (emitted) ++next_;
    return emitted;  // fail visibly on backpressure; never report a partial trial as success
  }
 private:
  std::uint64_t next_{};
};

class Work : public holoscan::Operator<> {
 public:
  holoscan::Input<std::uint64_t> in;
  holoscan::Output<std::uint64_t> out;
  void setup(holoscan::OperatorSpec& spec) override {
    spec.input(in, "in").queue_depth(64U);
    spec.output(out, "out");
  }
  holoscan::Contract contract() const override {
    holoscan::Contract result;
    result.trigger(holoscan::OnEach{in});
    return result;
  }
  holoscan::expected<void, holoscan::Error> compute(holoscan::ExecutionContext&) override {
    const auto start = now_ns();
    auto id = in.receive_data();
    if (!id) return holoscan::make_unexpected(std::move(id).error());
    auto trace = observation.take(*id);
    std::this_thread::sleep_for(100us);  // controlled host workload
    trace.append("work", start);
    observation.put(std::move(trace));
    return out.emit(*id);
  }
};

class Sink : public holoscan::Operator<> {
 public:
  holoscan::Input<std::uint64_t> in;
  void setup(holoscan::OperatorSpec& spec) override { spec.input(in, "in").queue_depth(64U); }
  holoscan::Contract contract() const override {
    holoscan::Contract result;
    result.trigger(holoscan::OnEach{in});
    return result;
  }
  holoscan::expected<void, holoscan::Error> compute(holoscan::ExecutionContext&) override {
    const auto start = now_ns();
    auto id = in.receive_data();
    if (!id) return holoscan::make_unexpected(std::move(id).error());
    auto trace = observation.take(*id);
    trace.append("sink", start);
    observation.logger->write(trace);
    {
      const std::lock_guard lock{observation.mutex};
      ++observation.received;
    }
    observation.ready.notify_all();
    return {};
  }
};
}  // namespace

int main() {
  try {
    if (const char* value = std::getenv("HOLOSCAN_NUM_SOURCE_MESSAGES")) {
      const std::string text{value};
      if (text.empty() || text.find_first_not_of("0123456789") != text.npos) {
        throw std::invalid_argument("message count must be a positive integer");
      }
      observation.limit = std::stoull(text);
      if (!observation.limit || observation.limit > 1000000) {
        throw std::invalid_argument("example supports 1 to 1000000 messages");
      }
    }
    observation.logger = std::make_unique<holoscan_benchmark::FlowLogger>();
    holoscan::Graph graph{"flow-tracking"};
    const auto source = graph.op<Source>("source");
    const auto work = graph.op<Work>("work");
    const auto sink = graph.op<Sink>("sink");
    graph.add_flow(source->out, work->in, holoscan::ConnectionOptions{.queue_depth = 64U});
    graph.add_flow(work->out, sink->in, holoscan::ConnectionOptions{.queue_depth = 64U});
    graph.set_default_clock(graph.add_clock<holoscan::RealtimeClock>("clock"));
    const auto plan = holoscan::compile(graph);
    if (!plan.ok()) { std::cerr << plan.json() << '\n'; return 1; }
    auto session = holoscan::run_async(plan);
    bool complete;
    {
      std::unique_lock lock{observation.mutex};
      complete = observation.ready.wait_for(lock, 5s + 5ms * observation.limit, [] {
        return observation.received == observation.limit;
      });
    }
    session.request_stop();
    session.wait();
    observation.logger->close();
    if (!complete || session.termination() != holoscan::RunTermination::kStopped ||
        !session.diagnostics().empty() || observation.received != observation.limit) {
      std::cerr << "flow-tracking run failed or incomplete\n";
      return 1;
    }
    std::cout << "Tracked " << observation.received << " messages through source -> work -> sink\n";
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
