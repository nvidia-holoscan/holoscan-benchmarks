# Benchmark catalog

This directory contains benchmark workloads, experiment scenarios, and published
results for Holoscan applications and operators. Each project has its own README
with its measurement procedure and environment requirements.

| Benchmark | What it measures | Available here |
| --- | --- | --- |
| [Model benchmarking](model_benchmarking/README.md) | Parallel inference workloads on a video stream | C++ and Python applications and configuration |
| [Real-time thread scheduling](realtime_threads_benchmarking/README.md) | Operator timing under competing CPU workloads | C++ benchmark, plotting script, and example results |
| [Green context benchmarking](green_context_benchmarking/README.md) | CUDA kernel launch-start and execution timing under GPU contention | C++/CUDA benchmark and reported results |
| [Exclusive display](exclusive_display/README.md) | Application latency with exclusive and default display modes | Published study and plots |
| [Release benchmarking](release_benchmarking/README.md) | Endoscopy Tool Tracking and Multi-AI Ultrasound latency across release configurations | HoloHub scenario runner, report templates, and published reports |

## Read results

Start with a project's README or one of the
[release reports](release_benchmarking/README.md#previous-holoscan-release-benchmark-reports).
Reading reports does not require the SDK or a GPU. Use each report's platform,
SDK version, application configuration, and methodology when interpreting its
measurements.

## Run a benchmark

Follow the selected project's README for hardware, SDK, data, build, and runtime
requirements. HoloHub commands require a separate HoloHub checkout; the
[repository README](../README.md#build-and-run) also shows a standalone CMake
build example.

## Benchmark your own code or contribute

Use the shared [benchmark tools](../benchmark_tools/README.md) to measure your
own application or operator. See [CONTRIBUTING.md](../CONTRIBUTING.md) for where
to put a new benchmark and what information to include with its results.
