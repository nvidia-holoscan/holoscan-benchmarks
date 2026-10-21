# Benchmark tools

Reusable collection and analysis tools for Holoscan SDK 5.x, using 5.0.0 as the
baseline. Workload-specific benchmarks belong in the
[benchmark directory](../benchmarks/README.md).

| Purpose | Tool |
| --- | --- |
| Explicit per-message flow tracing | [C++](flow_benchmarking/flow_tracking.hpp), [Python](flow_benchmarking/flow_tracking.py) |
| Holoscan SDK 5 tensor metadata, fan-out, and aligned join | [tensor example](flow_benchmarking/examples/tensor_flow_tracking.cpp), [correlation helper](flow_benchmarking/sdk_flow_tracking.hpp) |
| Minimal Holoscan SDK 5 Graph example | [flow_tracking.cpp](flow_benchmarking/examples/flow_tracking.cpp) |
| Repeated trials with failure detection and optional GPU monitoring | [benchmark.py](flow_benchmarking/benchmark.py) |
| End-to-end statistics, CSV export, and CDFs | [analyze.py](flow_benchmarking/analyze.py) |
| Operator and edge timing graphs | [app_perf_graph.py](flow_benchmarking/app_perf_graph.py) |
| Historical statistic plots | [generate_bar_graph.py](flow_benchmarking/generate_bar_graph.py), [bar_plot_avg_datewise.py](flow_benchmarking/bar_plot_avg_datewise.py), [bar_plot_generic_datewise.py](flow_benchmarking/bar_plot_generic_datewise.py) |

Start with the [Holoscan SDK 5 flow tracking guide](flow_benchmarking/README.md#quick-start),
or [instrument your own application](flow_benchmarking/README.md#benchmark-your-own-application).
Analysis also reads legacy Holoscan SDK logs and needs no GPU or Holoscan SDK installation.

Holoscan SDK 5 graphs must explicitly record and propagate per-message timing; the runner
does not change operators or scheduling. See the guide's migration and timing limits.
