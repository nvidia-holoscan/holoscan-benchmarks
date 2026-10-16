// SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
// SDK 5: source -> {left, right} -> aligned join. Tensor data and SampleMetadata
// travel through the SDK; process-local provenance stays in a bounded registry.
#include "sdk_flow_tracking.hpp"

#include <holoscan/core/compile.hpp>
#include <holoscan/core/execution_context.hpp>
#include <holoscan/core/graph.hpp>
#include <holoscan/core/operator.hpp>
#include <holoscan/core/operator_spec.hpp>
#include <holoscan/core/run.hpp>
#include <holoscan/core/temporal_contract.hpp>
#include <holoscan/time/realtime_clock.hpp>

#if __has_include(<holoscan/core/tensor_contract.hpp>)
#include <holoscan/core/tensor_contract.hpp>
#define FLOW_HAS_TENSOR_CONTRACT 1
#else
#define FLOW_HAS_TENSOR_CONTRACT 0
#endif

#include <array>
#include <atomic>
#include <condition_variable>
#include <iostream>
#include <memory>
#include <unistd.h>

namespace {
using namespace std::chrono_literals;
using holoscan_benchmark::FlowTrace;
using holoscan_benchmark::forward_flow_metadata;
using holoscan_benchmark::now_ns;
constexpr std::array<std::int64_t, 1> kShape{1};
constexpr DLDataType kDtype{kDLUInt, 64, 1};
constexpr std::uint32_t kQueueDepth = 32;
#if FLOW_HAS_TENSOR_CONTRACT
using TensorLayout = holoscan::TensorRepresentation;
#else
using TensorLayout = holoscan::TensorPortLayout;
#endif
constexpr TensorLayout kLayout = [] {
  TensorLayout layout{};
  layout.memory_kind = holoscan::MemoryKind::kHost;
  layout.dtype = kDtype;
  layout.rank = 1;
  return layout;
}();

void declare_input(holoscan::OperatorSpec& spec, holoscan::Input<holoscan::Tensor>& input,
                   const char* name) {
  auto& builder = spec.input(input, name).queue_depth(kQueueDepth);
#if FLOW_HAS_TENSOR_CONTRACT
  holoscan::TensorInputSpec input_spec{};
  input_spec.representation = kLayout;
  builder.expects_tensor(input_spec);
#else
  builder.expects_tensor(kLayout);
#endif
}

void declare_output(holoscan::OperatorSpec& spec, holoscan::Output<holoscan::Tensor>& output) {
  auto& builder = spec.output(output, "out");
#if FLOW_HAS_TENSOR_CONTRACT
  holoscan::TensorOutputSpec output_spec{};
  output_spec.representation = kLayout;
  output_spec.bounds = holoscan::tensor_bounds(sizeof(std::uint64_t));
  output_spec.storage = holoscan::TensorOutputStorage::kRuntimePool;
  builder.produces_tensor(output_spec);
#else
  // The installed 5.0.0 preview uses the earlier public Tensor declaration API.
  builder.produces_tensor(kLayout).tensor_allocation(
      holoscan::TensorAllocationBounds{.max_rank = 1, .max_byte_span = sizeof(std::uint64_t)});
#endif
}

holoscan::expected<holoscan::TensorOutputLoan, holoscan::Error> make_tensor(
    holoscan::Output<holoscan::Tensor>& output, std::uint64_t value) {
  auto loan = output.allocate_tensor(holoscan::TensorLoanRequest{.shape = kShape, .dtype = kDtype});
  if (!loan) return holoscan::make_unexpected(std::move(loan).error());
  auto written = loan->write_host_and_commit([value](const holoscan::TensorOutputWriteGuard& writer)
      -> holoscan::expected<void, holoscan::Error> {
    auto* data = writer.data_as<std::uint64_t>();
    if (!data || writer.byte_size() != sizeof(value)) {
      return holoscan::make_unexpected(
          holoscan::Error{holoscan::ErrorCode::kInvalidArgument, "invalid host tensor write"});
    }
    *data = value;
    return {};
  });
  if (!written) return holoscan::make_unexpected(std::move(written).error());
  return std::move(*loan);
}

std::uint64_t check_sample(const holoscan::Sample<holoscan::Tensor>& sample,
                           std::uint64_t increment) {
  const auto& metadata = sample.metadata;
  const auto* value = sample.data.data_as<std::uint64_t>();
  if (!metadata.trace_id || metadata.frame_id != metadata.trace_id ||
      !metadata.source_clock_id.valid() || !value || sample.data.size() != 1 ||
      sample.data.device().device_type != kDLCPU || *value != metadata.frame_id + increment) {
    throw std::runtime_error("tensor payload or trace/frame/capture metadata was not preserved");
  }
  return metadata.trace_id;
}

struct RunState {
  RunState(std::uint64_t count, bool enabled) : limit(count), tracking(enabled) {
    if (tracking) logger = std::make_unique<holoscan_benchmark::FlowLogger>();
  }
  const std::uint64_t limit;
  const bool tracking;
  holoscan_benchmark::TraceRegistry traces{256};
  std::unique_ptr<holoscan_benchmark::FlowLogger> logger;
  std::atomic<std::uint64_t> emitted{};
  std::mutex mutex;
  std::condition_variable ready;
  std::uint64_t completed{};
  std::uint64_t path_records{};
};

// Graph factories reject shared-pointer captures. This executable runs exactly
// one graph at a time; main owns this state through session.wait(). A concurrent
// multi-session application must provide its own run-to-state lookup instead.
RunState* active_run{};
struct RunBinding {
  explicit RunBinding(RunState& state) {
    if (active_run) throw std::logic_error("a tensor benchmark run is already active");
    active_run = &state;
  }
  ~RunBinding() { active_run = nullptr; }
  RunBinding(const RunBinding&) = delete;
  RunBinding& operator=(const RunBinding&) = delete;
};

class Source : public holoscan::Operator<> {
 public:
  Source() : state_(*active_run) {}
  holoscan::Output<holoscan::Tensor> out;
  void setup(holoscan::OperatorSpec& spec) override { declare_output(spec, out); }
  holoscan::Contract contract() const override {
    holoscan::Contract result;
    result.trigger(holoscan::OnClock{.period = 1ms});
    return result;
  }
  holoscan::expected<void, holoscan::Error> compute(holoscan::ExecutionContext& context) override {
    if (next_ > state_.limit) return {};
    const auto start = state_.tracking ? now_ns() : 0;
    auto loan = make_tensor(out, next_);
    if (!loan) return holoscan::make_unexpected(std::move(loan).error());
    if (state_.tracking) {
      FlowTrace trace{next_};
      trace.append("source", start);
      state_.traces.put("left", trace);
      state_.traces.put("right", std::move(trace));
    }
    // The source creates a real frame at its activation time. Both branches
    // preserve this coordinate so OnAligned selects the corresponding pair.
    auto result = out.emit(std::move(*loan), holoscan::EmitOptions{
        .capture_time = context.activation_time(), .frame_id = next_,
        .trace = holoscan::TraceContext::root(next_)});
    if (result) state_.emitted.store(next_++);
    return result;
  }
 private:
  RunState& state_;
  std::uint64_t next_{1};  // SDK trace identity zero means absent.
};

class Transform : public holoscan::Operator<> {
 public:
  Transform(std::string branch, std::uint64_t increment)
      : state_(*active_run), branch_(std::move(branch)), increment_(increment) {}
  holoscan::Input<holoscan::Tensor> in;
  holoscan::Output<holoscan::Tensor> out;
  void setup(holoscan::OperatorSpec& spec) override {
    declare_input(spec, in, "in");
    declare_output(spec, out);
  }
  holoscan::Contract contract() const override {
    holoscan::Contract result;
    result.trigger(holoscan::OnEach{in});
    return result;
  }
  holoscan::expected<void, holoscan::Error> compute(holoscan::ExecutionContext&) override {
    const auto start = state_.tracking ? now_ns() : 0;
    auto sample = in.receive();  // receive_data() would discard the metadata.
    if (!sample) return holoscan::make_unexpected(std::move(sample).error());
    const auto id = check_sample(*sample, 0);
    auto loan = make_tensor(out, id + increment_);
    if (!loan) return holoscan::make_unexpected(std::move(loan).error());
    if (state_.tracking) {
      auto trace = state_.traces.take(id, branch_);
      trace.append(branch_, start);
      state_.traces.put(branch_, std::move(trace));
    }
    return out.emit(std::move(*loan), forward_flow_metadata(sample->metadata));
  }
 private:
  RunState& state_;
  std::string branch_;
  std::uint64_t increment_;
};

class Join : public holoscan::Operator<> {
 public:
  Join() : state_(*active_run) {}
  holoscan::Input<holoscan::Tensor> left, right;
  void setup(holoscan::OperatorSpec& spec) override {
    declare_input(spec, left, "left");
    declare_input(spec, right, "right");
  }
  holoscan::Contract contract() const override {
    holoscan::Contract result;
    result.trigger(holoscan::OnAligned{.ports = holoscan::ports(left, right), .window = 0ns});
    result.input(left, holoscan::Exact{});
    result.input(right, holoscan::Exact{});
    return result;
  }
  holoscan::expected<void, holoscan::Error> compute(holoscan::ExecutionContext&) override {
    const auto start = state_.tracking ? now_ns() : 0;
    auto a = left.receive();
    auto b = right.receive();
    if (!a) return holoscan::make_unexpected(std::move(a).error());
    if (!b) return holoscan::make_unexpected(std::move(b).error());
    const auto id = check_sample(*a, 1);
    if (check_sample(*b, 2) != id || a->metadata.capture_time() != b->metadata.capture_time()) {
      throw std::runtime_error("join selected inconsistent input provenance");
    }
    if (state_.tracking) {
      auto left_trace = state_.traces.take(id, "left");
      auto right_trace = state_.traces.take(id, "right");
      const auto end = now_ns();
      left_trace.append("join", start, end);
      right_trace.append("join", start, end);
      state_.logger->write(left_trace);
      state_.logger->write(right_trace);
      state_.path_records += 2;
    }
    {
      const std::lock_guard lock{state_.mutex};
      if (id != state_.completed + 1) throw std::runtime_error("missing or duplicate frame");
      ++state_.completed;
    }
    state_.ready.notify_all();
    return {};
  }
 private:
  RunState& state_;
};
}  // namespace

int main(int argc, char** argv) {
  try {
    const bool tracking = argc == 1;
    if (argc > 2 || (argc == 2 && std::string_view{argv[1]} != "--no-tracking")) {
      throw std::invalid_argument("usage: tensor_flow_tracking [--no-tracking]");
    }
    std::uint64_t limit = 100;
    if (const char* value = std::getenv("HOLOSCAN_NUM_SOURCE_MESSAGES")) {
      const std::string text{value};
      if (text.empty() || text.find_first_not_of("0123456789") != text.npos) {
        throw std::invalid_argument("message count must be a positive integer");
      }
      limit = std::stoull(text);
      if (!limit || limit > 1000000) throw std::invalid_argument("count must be 1 to 1000000");
    }
    RunState state{limit, tracking};
    RunBinding binding{state};
    // This SDK preview derives host Tensor transport service names from the
    // graph identity. Concurrent benchmark processes need distinct identities.
    holoscan::Graph graph{"tensor-flow-tracking-" + std::to_string(::getpid())};
    const auto source = graph.op<Source>("source");
    const auto left = graph.op<Transform>("left", "left", 1);
    const auto right = graph.op<Transform>("right", "right", 2);
    const auto join = graph.op<Join>("join");
    holoscan::ConnectionOptions connection{};
    connection.queue_policy = holoscan::QueuePolicy::kBlocking;
    connection.queue_depth = kQueueDepth;
    graph.add_flow(source->out, left->in, connection);
    graph.add_flow(source->out, right->in, connection);
    graph.add_flow(left->out, join->left, connection);
    graph.add_flow(right->out, join->right, connection);
    graph.set_default_clock(graph.add_clock<holoscan::RealtimeClock>("clock"));
    const auto plan = holoscan::compile(graph);
    if (!plan.ok()) { std::cerr << plan.json() << '\n'; return 1; }
    const auto started = std::chrono::steady_clock::now();
    auto session = holoscan::run_async(plan);
    const auto deadline = started + 5s + 5ms * limit;
    bool complete = false;
    {
      std::unique_lock lock{state.mutex};
      while (std::chrono::steady_clock::now() < deadline && session.is_running()) {
        if (state.ready.wait_for(lock, 50ms, [&] { return state.completed == limit; })) {
          complete = true;
          break;
        }
      }
    }
    session.request_stop();
    session.wait();
    const double seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    if (state.logger) state.logger->close();
    for (const auto& diagnostic : session.diagnostics()) std::cerr << diagnostic.token << '\n';
    if (!complete || state.emitted != limit || state.completed != limit ||
        state.traces.pending() || state.path_records != (tracking ? 2 * limit : 0) ||
        session.termination() != holoscan::RunTermination::kStopped || !session.diagnostics().empty()) {
      throw std::runtime_error("tensor flow run failed or did not produce every expected path");
    }
    // Includes run startup/shutdown and log writes. Both modes execute the same
    // paced graph and payload checks; this is not an unpaced throughput test.
    std::cout << std::boolalpha << "{\"tracking\":" << tracking
              << ",\"completed_frames\":" << state.completed
              << ",\"path_records\":" << state.path_records
              << ",\"pending_traces\":" << state.traces.pending()
              << ",\"wall_seconds\":" << seconds
              << ",\"frames_per_second\":" << limit / seconds << "}\n";
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
