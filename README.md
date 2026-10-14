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
| Measure your own application or operator, analyze logs, or create plots | [Measurement and analysis tools](benchmark_tools/README.md) |

Interpret results using each report's hardware, SDK version, workload, and
measurement procedure.

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

Follow the selected benchmark's README for its build tools and supported SDK
versions. For a benchmark with a standalone CMake entry point, adapt these
commands from the repository root, replacing `<benchmark>` with its directory
and setting `CMAKE_PREFIX_PATH` to your SDK installation:

```bash
cmake -S benchmarks/<benchmark> -B build/<benchmark> \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=/path/to/holoscan/install
cmake --build build/<benchmark> --parallel
```

Add any options required by the benchmark, then use its documented run command
to configure the workload and collect measurements. Benchmarks using other
build systems provide their own instructions.

## Analyze existing logs

Use the [measurement and analysis tools](benchmark_tools/README.md) to turn
recorded measurements into statistics and plots. Follow the selected tool's
documentation for supported input formats, dependencies, and commands. To
collect new measurements, follow its instrumentation instructions and the
application's runtime requirements.

## Related projects and contributions

Find workloads in [Holoscan Applications](https://github.com/nvidia-holoscan/holoscan-applications),
learn development techniques in [Holoscan Tutorials](https://github.com/nvidia-holoscan/holoscan-tutorials),
and discover additional projects through HoloHub.

To add a benchmark, improve measurement tools, or publish reproducible results,
see [CONTRIBUTING.md](CONTRIBUTING.md).

Licensed under [Apache 2.0](LICENSE).
