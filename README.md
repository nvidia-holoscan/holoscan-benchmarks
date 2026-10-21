# Holoscan Benchmarks

Measurement and analysis tools for
[NVIDIA Holoscan SDK](https://github.com/nvidia-holoscan/holoscan-sdk) 5.x,
using Holoscan SDK 5.0.0 as the baseline. Use them to instrument applications, collect
per-message timings, compare configurations, and analyze latency.

See the [benchmark directory overview](benchmarks/README.md) for the scope and
measurement practices of workload-specific benchmarks.

This repository is part of the Holoscan ecosystem and is listed in the
[HoloHub registry](https://github.com/nvidia-holoscan/holohub).

## Getting started

```bash
git clone https://github.com/nvidia-holoscan/holoscan-benchmarks.git
cd holoscan-benchmarks
```

Start with the [measurement and analysis tools](benchmark_tools/README.md).
The [Holoscan SDK 5 flow-tracking quick start](benchmark_tools/flow_benchmarking/README.md#quick-start)
includes build, collection, and analysis commands for the C++ examples. It
requires a Holoscan SDK 5.0.0 development environment, CMake 4+, a C++20 compiler, and
the Holoscan SDK's runtime dependencies.

To measure your own workload, follow the
[instrumentation guide](benchmark_tools/flow_benchmarking/README.md#benchmark-your-own-application).
The runner accepts an explicit application command. Instrumentation and message
limits must be implemented by the application.

## Analyze existing logs

Follow the [flow benchmarking guide](benchmark_tools/flow_benchmarking/README.md)
to generate statistics, CSV files, timing graphs, and plots. Analysis supports
both the Holoscan SDK 5 examples' JSONL records and legacy Holoscan SDK flow logs, and does not
require a Holoscan SDK or GPU installation.

## Related projects and contributions

Find workloads in [Holoscan Applications](https://github.com/nvidia-holoscan/holoscan-applications),
learn development techniques in [Holoscan Tutorials](https://github.com/nvidia-holoscan/holoscan-tutorials),
and discover additional projects through HoloHub.

To add a validated Holoscan SDK 5 benchmark or improve measurement tools, see
[CONTRIBUTING.md](CONTRIBUTING.md).

Licensed under [Apache 2.0](LICENSE).
