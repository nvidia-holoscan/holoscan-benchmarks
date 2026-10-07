# Holoscan Benchmarks

Benchmarks, analysis tools, and published results for the NVIDIA Holoscan SDK.

Benchmark workloads, scenarios, and published results live under
[`benchmarks/`](benchmarks/README.md). Reusable measurement and analysis tools
live under [`benchmark_tools/`](benchmark_tools/README.md).

## Start here

| What you want to do | Where to start |
| --- | --- |
| Read published results | [Benchmark catalog](benchmarks/README.md); no installation is required to read reports. |
| Run an existing benchmark | Choose a benchmark in the [catalog](benchmarks/README.md), then follow its README. |
| Benchmark your own application or operator | [Flow benchmarking guide](benchmark_tools/flow_benchmarking/README.md#benchmark-your-own-application) |
| Contribute a benchmark or improve the tools | [Contributing guide](CONTRIBUTING.md) |

## Setup

To run benchmarks, use a Linux environment with the Holoscan SDK and the
hardware, CUDA version, models, and data required by the selected benchmark.
Check its README for supported versions and any additional dependencies.

Some benchmark guides describe HoloHub workflows. Commands beginning with
`./holohub` require a separate HoloHub checkout and its application and data
setup. This repository does not include that launcher.

For workflows that need CLI support, install
[Holoscan CLI](https://github.com/nvidia-holoscan/holoscan-cli) with pip.
The `holoscan-cli` package provides the `holoscan` command for building,
running, and managing containers for Holoscan projects.

Run the following commands from the repository root, using a Python version
supported by the CLI release:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install holoscan-cli
holoscan --help
```

Use `holoscan <command> --help` for command-specific options.

## Build and run

The C++ benchmarks have standalone CMake entry points. For example, with a
C++17 compiler, CMake 3.20+, and Holoscan SDK 3.5+ installed, run from the
repository root:

```bash
cmake -S benchmarks/realtime_threads_benchmarking -B build/realtime \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=/opt/nvidia/holoscan
cmake --build build/realtime -j
./build/realtime/realtime_thread_benchmark --help
```

Set `CMAKE_PREFIX_PATH` to your Holoscan SDK installation and use a separate
build directory for each benchmark. Follow the selected benchmark's README
to configure the workload and collect measurements.

## Analyze existing logs

Existing flow logs can be analyzed without a GPU or the Holoscan SDK.
From the repository root, create and activate a Python virtual environment
if needed, then install the analysis dependencies:

```bash
python -m pip install numpy matplotlib
python benchmark_tools/flow_benchmarking/analyze.py --help
```

To collect new measurements, follow the
[flow benchmarking guide](benchmark_tools/flow_benchmarking/README.md) for
application instrumentation, HoloHub runner setup, and optional monitoring and
visualization dependencies.

## Local checks

Run these checks from the repository root with Python 3.10+ and Bash.
They do not require a GPU, the Holoscan SDK, or third-party Python packages:

```bash
python3 .github/scripts/check.py
python3 -m unittest discover -s benchmark_tools/flow_benchmarking/tests -v
```

GitHub Actions runs the same Python, JSON, and shell syntax checks and
log-parser tests. GPU builds, runtime behavior, and performance measurements
require the benchmark-specific environment and are not covered by CI.

Licensed under [Apache 2.0](LICENSE).
