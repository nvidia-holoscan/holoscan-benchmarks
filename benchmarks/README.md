# Benchmarks for Holoscan SDK 5.x

This directory is for benchmarks of Holoscan SDK 5.x applications and operators,
using SDK 5.0.0 as the baseline. Benchmarks evaluate latency, throughput,
resource utilization, and the effects of runtime configuration through
reproducible workloads.

Each benchmark should document what it measures, its hardware and software
requirements, required models and input data, and build and run instructions.
Measurement procedures should explain warm-up, sample counts, repetitions, and
how to interpret the results. Compare measurements in the context of their
hardware, SDK version, and workload configuration.

Use the [shared measurement and analysis tools](../benchmark_tools/README.md)
to instrument workloads, collect timings, and analyze results. Application
workloads can come from the SDK or
[Holoscan Applications](https://github.com/nvidia-holoscan/holoscan-applications).
See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidance on adding a benchmark.

For benchmarks targeting Holoscan SDK releases before 5.x, see the
[HoloHub archive-4x branch](https://github.com/nvidia-holoscan/holohub/tree/archive-4x).
