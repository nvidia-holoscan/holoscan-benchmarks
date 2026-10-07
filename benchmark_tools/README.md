# Benchmark tools

Reusable tools for measuring and analyzing Holoscan applications. Benchmark
workloads, scenario definitions, and published results are listed in the
[benchmark catalog](../benchmarks/README.md).

## Available tools

The [flow benchmarking tools](flow_benchmarking/README.md) include:

| Purpose | Files |
| --- | --- |
| Run repeated measurements and optional GPU utilization monitoring | [benchmark.py](flow_benchmarking/benchmark.py) |
| Enable flow tracking in C++ or Python applications | [benchmark.hpp](flow_benchmarking/benchmark.hpp), [benchmarked_application.py](flow_benchmarking/benchmarked_application.py) |
| Parse logs and calculate latency statistics | [log_parser.py](flow_benchmarking/log_parser.py), [analyze.py](flow_benchmarking/analyze.py) |
| Visualize operator and connection timings | [app_perf_graph.py](flow_benchmarking/app_perf_graph.py) |
| Plot exported statistics | [generate_bar_graph.py](flow_benchmarking/generate_bar_graph.py), [bar_plot_avg_datewise.py](flow_benchmarking/bar_plot_avg_datewise.py), [bar_plot_generic_datewise.py](flow_benchmarking/bar_plot_generic_datewise.py) |

The instrumentation, source-patching helpers, documentation, and tests stay
together in `flow_benchmarking/` so these scripts can be used directly from a
checkout.

## Analyze existing logs

Run from the repository root in a Python environment with the analysis
dependencies installed. This workflow does not require a GPU or the Holoscan SDK:

```bash
python -m pip install numpy matplotlib
python benchmark_tools/flow_benchmarking/analyze.py --help
python benchmark_tools/flow_benchmarking/analyze.py \
    -g /path/to/logs/logger_greedy_*.log MyApplication \
    --avg --max --median --percentile 95 99
```

The analyzer discards the first and last ten samples of each path in each input
log. Provide enough samples for the statistics to be meaningful. Its CSV export
contains the first nonempty path's statistics for each group; use the console
output to inspect statistics for all paths.

## Collect new measurements

Follow [Benchmark your own application](flow_benchmarking/README.md#benchmark-your-own-application)
to instrument and run your application directly, or the
[HoloHub workflow](flow_benchmarking/README.md#environment-setup) for existing
HoloHub applications. Collection requires the application's SDK, hardware, and
runtime dependencies; monitoring and graph visualization have additional
dependencies documented in that guide.

## Contribute

See the [contributing guide](../CONTRIBUTING.md) for placement rules and local
checks. Keep reusable measurement functionality here and workload-specific
behavior with its benchmark.
