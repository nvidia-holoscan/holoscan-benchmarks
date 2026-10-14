# Holoscan Benchmarks

Benchmarks, measurement tools, and published results for the
[NVIDIA Holoscan SDK](https://github.com/nvidia-holoscan/holoscan-sdk). Use them
to evaluate application and operator performance, compare configurations, and
analyze latency.

This repository is part of the Holoscan ecosystem and is listed in the
[HoloHub registry](https://github.com/nvidia-holoscan/holohub). Use this
independent repository directly to read reports, build benchmarks, or analyze
your own measurements.

## Start here

| What you want to do | Where to start |
| --- | --- |
| Read published results | [Benchmark catalog](benchmarks/README.md); reports need no SDK or GPU. |
| Run an existing benchmark | Choose a workload in the [catalog](benchmarks/README.md), then follow its README. |
| Benchmark your own application or operator | [Flow benchmarking guide](benchmark_tools/flow_benchmarking/README.md#benchmark-your-own-application) |
| Analyze measurements or create plots | [Measurement and analysis tools](benchmark_tools/README.md) |

The catalog covers model inference, CPU thread scheduling, CUDA green
contexts, display latency, and release comparisons. Interpret results using
each report's hardware, SDK version, workload, and measurement procedure.

## Getting started

Clone this repository:

```bash
git clone https://github.com/nvidia-holoscan/holoscan-benchmarks.git
cd holoscan-benchmarks
```

To collect measurements, prepare the Linux environment, SDK, hardware, models,
and data required by the selected benchmark. Its README describes supported
versions and any additional dependencies.

Some guides and runners use applications from the former HoloHub source
collection. Commands beginning with `./holohub` require a separate HoloHub
checkout containing the referenced applications and launcher, plus their data
setup. Follow the guide's version-specific instructions for those workflows.

## Build and run

For a standalone CMake example, build the
[real-time thread scheduling benchmark](benchmarks/realtime_threads_benchmarking/README.md).
With a C++17 compiler, CMake 3.20+, and Holoscan SDK 3.5+ installed, run from the
repository root:

```bash
cmake -S benchmarks/realtime_threads_benchmarking -B build/realtime \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=/opt/nvidia/holoscan
cmake --build build/realtime -j
./build/realtime/realtime_thread_benchmark --help
```

Set `CMAKE_PREFIX_PATH` to your SDK installation. Follow the benchmark's README
to choose a workload, collect measurements, and plot results. Other benchmarks
have their own build and run instructions.

## Analyze existing logs

Flow logs can be analyzed without a GPU or the SDK. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install numpy matplotlib
python benchmark_tools/flow_benchmarking/analyze.py --help
```

See the [analysis examples](benchmark_tools/README.md#analyze-existing-logs)
for latency statistics and plots. To collect new logs from your own code, follow
the [application instrumentation guide](benchmark_tools/flow_benchmarking/README.md#benchmark-your-own-application).

## Related projects and contributions

Find workloads in [Holoscan Applications](https://github.com/nvidia-holoscan/holoscan-applications),
learn development techniques in [Holoscan Tutorials](https://github.com/nvidia-holoscan/holoscan-tutorials),
and discover additional projects through HoloHub.

To add a benchmark, improve measurement tools, or publish reproducible results,
see [CONTRIBUTING.md](CONTRIBUTING.md).

Licensed under [Apache 2.0](LICENSE).
