# Flow benchmarking for Holoscan SDK 5.0.0

Collect per-message host timings, run repeated trials, and analyze every recorded
path. The SDK 5 integration uses `Graph`, typed ports, `compile()`, and
`RunSession`. It does not depend on the removed SDK 4 `Application`,
`CountCondition`, scheduler classes, or `Application.track()` APIs.

## Quick start

From this repository's root, in an SDK 5.0.0 development environment with CMake
4+, a C++20 compiler, and the SDK's runtime dependencies:

```bash
cmake -S benchmark_tools/flow_benchmarking/examples \
    -B build/flow-tracking -DCMAKE_PREFIX_PATH=/absolute/path/to/sdk-install
cmake --build build/flow-tracking -j

python3 benchmark_tools/flow_benchmarking/benchmark.py \
    --run-command "$PWD/build/flow-tracking/tensor_flow_tracking" \
    -r 2 -i 2 -m 100 -d build/flow-results

python3 -m pip install -r benchmark_tools/flow_benchmarking/requirements.txt
python3 benchmark_tools/flow_benchmarking/analyze.py \
    -g build/flow-results/flow_*.jsonl SDK5 \
    --avg --max --median --percentile 95 99 \
    --output-csv build/flow-results/summary.csv
python3 benchmark_tools/flow_benchmarking/app_perf_graph.py \
    build/flow-results/flow_*.jsonl -o build/flow-results/graph.dot
```

Use a **new output directory** for each invocation. The runner refuses existing
trial artifacts. If the SDK libraries are outside the loader's search path,
add its `lib` directory to `LD_LIBRARY_PATH`. No GPU computation, models, video,
HoloHub checkout, or display is used by this example; the SDK itself may require
CUDA runtime libraries.

The [tensor example](examples/tensor_flow_tracking.cpp) sends host tensors through
`source → {left, right} → join`. Each transform allocates a new tensor, preserves
the input's trace/frame/capture metadata, and the aligned join checks both inputs.
Each completed frame produces two source-to-join paths. The graph uses bounded
blocking queues; it fails on incomplete frames, incorrect payloads, missing
provenance, or leftover trace entries.
Its graph name includes the process ID to isolate SDK tensor channel service
names between simultaneous instances. Give concurrent instances of your own
graph distinct names when using the tested SDK build.

The smaller [scalar example](examples/flow_tracking.cpp) sends integer IDs through
`source → work → sink`. Application-owned state associates each ID with its
trace. The source emits the requested number of messages; the sink records every
arrival. Main waits for the sink count, explicitly stops and joins the session,
checks its termination/diagnostics, then closes the log. An incomplete run or
backpressure error fails the trial. Both examples are collection checks; replace
their work with your application's workload for performance measurements.

## Benchmark your own application

### Instrument explicit boundaries

Use [flow_tracking.hpp](flow_tracking.hpp) in C++ or
[flow_tracking.py](flow_tracking.py) in Python. They are small SDK-independent
writers, not automatic instrumentation of arbitrary operators. The C++ examples
provide SDK graph integration. The Python writer can be used from your
application's callbacks; it does not provide or emulate SDK Python bindings.

1. Assign a unique unsigned 64-bit ID to each source message within a run.
2. Record `now_ns()` when work starts in an operator.
3. Append its name, start, and end timestamp to that message's trace immediately
   before publication (at the sink, after consuming/processing the message).
4. Preserve the trace across each edge. Carry it in application metadata or
   correlate it through a bounded, synchronized application-owned ID table.
   `FlowTrace` is **not** itself a registered SDK port payload.
5. Write the completed trace at each sink; stop/join all callbacks before closing
   the writer. A failed log write must fail the measurement.

Python example for an application that already owns message correlation:

```python
from flow_tracking import FlowLogger, FlowTrace, now_ns

# Put benchmark_tools/flow_benchmarking on PYTHONPATH.
with FlowLogger() as logger:  # HOLOSCAN_FLOW_TRACKING_LOG_FILE, or flow.jsonl
    source_start = now_ns()
    trace = FlowTrace(message_id=1).append("source", source_start)
    # Pass/store trace alongside the actual application message.
    sink_start = now_ns()
    # Consume/process that message here.
    trace = trace.append("sink", sink_start)
    logger.write(trace)
```

In C++, construct `holoscan_benchmark::FlowTrace{id}`, call
`trace.append("operator", start_ns)` and `logger.write(trace)`. The logger creates
its file exclusively and flushes each complete record for live readers. Python
`append()` returns an immutable branch; C++ `append()` modifies the trace, so copy
it before branching. Logging is thread-safe; sharing a mutable trace is not.

For fan-out, copy the incoming trace into each branch. For fan-in, retain each
input's provenance and log each contributing source-to-sink path separately.
Do not overwrite one trace with another. A batching operator can complete
multiple message traces in one callback. Retire correlation entries for dropped
messages and bound outstanding state; the example's single-path ID table removes
each entry on receipt. The writer does not infer joins, drops, or paths.

For SDK C++ tensor graphs, [sdk_flow_tracking.hpp](sdk_flow_tracking.hpp) provides
`TraceRegistry(capacity)`, keyed by a nonzero SDK trace ID and an explicit branch
name. It rejects duplicate entries and capacity overflow; `take()` transfers a
branch to its consumer and `retire()` removes a known dropped branch. Create one
registry per run, copy provenance into every branch before publication, and take
each branch separately at a join. Queue drops are not detected automatically;
applications must account for them or fail the measurement on missing traces or
capacity exhaustion.

Use `receive()` to retain `SampleMetadata`. When publishing a replacement tensor,
pass `forward_flow_metadata(sample.metadata)` to `emit()` to preserve its trace ID,
frame ID, capture coordinate, and flags within that session. `receive_data()`
discards this metadata. The tensor example shows these calls and checks that
payload transformation preserves correlation through fan-out and fan-in.

### Timing contract and limits

- Records use process-local monotonic **nanoseconds**. Legacy SDK logs use
  **microseconds**. All reported latencies are **milliseconds**.
- Path latency is the last recorded end minus the first recorded start.
  Node timing is the explicitly instrumented interval; edge timing is the next
  start minus the previous end and includes queueing and scheduling delays.
- These are host intervals, not exact SDK callback durations or GPU kernel
  durations. The example ends the source/work interval before `emit()` and the
  sink interval before log I/O. Timestamping, correlation, copying, flushing, and
  logging add overhead; some falls between the measured intervals. Record these
  choices when comparing applications.
- Asynchronous CUDA work needs an explicit completion measurement if GPU
  completion is the desired endpoint. This tool does not synchronize CUDA.
- Never subtract timestamps from different processes or machines. Distributed
  clock synchronization, automatic operator wrapping, automatic join inference,
  and scheduler selection are outside this collector's scope.
- The writers allocate and perform file I/O; they are not hard-real-time probes.
  Use an appropriate separate tracing/profiling system for that requirement.

The tensor example also accepts `--no-tracking` for a baseline. Run it directly,
because the collection runner intentionally requires a nonempty log:

```bash
HOLOSCAN_NUM_SOURCE_MESSAGES=1000 build/flow-tracking/tensor_flow_tracking --no-tracking
```

Both modes print JSON with completed frames and wall time including graph
startup/shutdown. They execute the same payload checks and use a 1 ms source
period; that pacing limits throughput. Compare repeated runs with tracing
enabled/disabled in your actual workload to quantify instrumentation overhead.

### Run repeated trials

Run the application from its usual working directory:

```bash
python3 /path/to/benchmarks/benchmark_tools/flow_benchmarking/benchmark.py \
    --run-command '/path/to/my_app --my-option value' \
    -r 3 -i 2 -m 1000 --timeout 120 -d /path/to/new-results
```

The shell command is used exactly as supplied. Each process receives:

| Variable | Meaning |
| --- | --- |
| `HOLOSCAN_FLOW_TRACKING_LOG_FILE` | Absolute, unique `flow_<run>_<instance>.jsonl` path |
| `HOLOSCAN_NUM_SOURCE_MESSAGES` | Requested count; your application must implement it |
| `CUDA_VISIBLE_DEVICES` | Set only when `--gpu` is provided with a value other than `all` |

The runner records its command/configuration in `benchmark.json` and each child's
output in `console_<run>_<instance>.log`. Nonzero exits, timeouts, missing logs,
malformed records, and empty measurements fail the command. It verifies that
records exist, not that arbitrary applications honored the requested count:
branching, batching, and dropping can change the number of completed paths.
Launchers must wait for their workers before returning. Surviving processes in
the trial's process group are stopped and fail the trial; detached services
outside that process group must be managed separately by the application.

Optional physical GPU monitoring: install `nvitop`, then add `--monitor_gpu`.
Samples are written to `gpu_utilization_<run>.csv`; unavailable telemetry fails
explicitly. Utilization is not per-process and includes other GPU workloads.
No scheduler is substituted: configure execution policy in the SDK 5 graph.

## Analyze and visualize

`analyze.py` reads new JSONL and legacy `(operator,start_us,end_us) -> ...` logs.
By default it excludes ten warmup and ten tail records **per file and path**.
For a short smoke test, pass `--skip-begin 0 --discard-last 0`. An entirely empty
result is an error. Nearby sink timestamps are now distinct; only consecutive
exact legacy duplicates are removed. This intentionally corrects the old 20 μs
heuristic, which could remove real samples.

`--output-csv summary.csv` exports all groups/paths, sample counts, mean, min,
max, median, population standard deviation, p95, and p99. Empty paths get a count
of zero and blank statistics when other paths have data. Percentiles retain the
legacy sorted-index convention (`floor(n*p/100)`, capped at `n-1`), without
interpolation. Existing `--save-csv` exports remain for historical plotting
scripts; those files contain only the first nonempty path per group.

```bash
python3 benchmark_tools/flow_benchmarking/analyze.py \
    -g build/flow-results/flow_*.jsonl SDK5 \
    --draw-cdf-paths build/flow-results/cdf.png --no-display-graphs

# Refresh graph.dot once per second; view with Graphviz or an optional xdot install.
python3 benchmark_tools/flow_benchmarking/app_perf_graph.py \
    --live build/flow-results -o build/flow-results/graph.dot
```

Graphs use individual node/edge sample counts and count shared branch prefixes
once per message within each file. These are **message-weighted** observations,
not unique callback counts: a 10 ms callback handling two messages and a 1 ms
callback handling one message have a 7 ms message-weighted mean, not a 5.5 ms
callback mean. Record explicit invocation IDs with a separate profiler when
callback-level statistics are required. Operator names containing the path
separator or backslashes are escaped in CSV/CDF path labels to keep paths distinct.
Live mode excludes incomplete final lines and
recomputes snapshots, so warmup/tail handling matches offline analysis even when
files grow or are replaced. Refresh cost grows with log size. An empty live
snapshot leaves the last graph in place until new samples arrive.

## Migration and validation

Removed the SDK 1–4 `BenchmarkedApplication` helpers and regex-based patch/restore
scripts. They depended on APIs absent from SDK 5, rewrote source files, imposed
count conditions on intermediate operators, and changed application scheduling.
The old `-a/--holohub-application`, `--sched`, `--language`, and worker-count runner
options are replaced by an explicit `--run-command`. The historical release
suite's collection recipes need SDK 5 workload instrumentation before reuse;
existing log analysis and plotting remain supported.

Validated on aarch64 using the local SDK package reporting 5.0.0, C++ Graph API,
GCC 13.3, CUDA 13 runtime, and the SDK development container. Both examples passed
three runs of two simultaneous instances, with 1,000 frames per instance:
6,000 scalar records and 12,000 tensor path records. CSV, CDF, and DOT generation
passed, including exact retained counts (5,880 per path) and deduplication of
shared source/join observations. All 33 CPU tests and four SDK integration tests
passed. The newer tensor-contract header branch was also syntax-checked; runtime
validation used the installed SDK's tensor declaration API.

This validates host flow collection and analysis. GPU completion timing, full
endoscopy/inference workloads, SDK Python graph integration, distributed clock
correlation, and other application topologies have not been validated here.

```bash
python3 .github/scripts/check.py
python3 -m unittest discover -s benchmark_tools/flow_benchmarking/tests -v
# Install requirements.txt to also run the analysis CLI tests.
```

The CPU suite exercises both writers, branch copies, units, malformed logs,
per-path trimming, graph statistics, subprocess failures/timeouts, and CSV export.
The C++ writer test compiles with `g++`; runtime graph validation requires SDK 5.
Run the SDK tests in the same SDK development environment used for the build:

```bash
HOLOSCAN_SDK_PREFIX=/absolute/path/to/sdk-install \
HOLOSCAN_TENSOR_FLOW_EXECUTABLE="$PWD/build/flow-tracking/tensor_flow_tracking" \
    python3 -m unittest discover -s benchmark_tools/flow_benchmarking/tests \
    -p test_sdk_flow_tracking.py -v
```

These compile the metadata/correlation helper and exercise tensor transformation,
fan-out, aligned joining, four simultaneous instances, and the untracked baseline.
Without these environment variables, SDK-dependent tests are explicitly skipped.
