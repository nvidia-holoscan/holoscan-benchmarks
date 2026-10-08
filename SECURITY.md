# Security Policy: Holoscan Benchmarks

## Reporting a Vulnerability

If you discover a potential security vulnerability, **do not open a public issue,
pull request, or discussion**.

- **Web (preferred):** Report it through the
  [NVIDIA Vulnerability Disclosure Program](https://www.nvidia.com/en-us/security/).
- **Email:** Send details to [psirt@nvidia.com](mailto:psirt@nvidia.com). For
  encrypted communication, use the
  [NVIDIA public PGP key](https://www.nvidia.com/en-us/security/pgp-key).
- **GitHub:** Use this repository's **Security** tab to submit a private report
  on `nvidia-holoscan/holoscan-benchmarks`.

Include the project name and affected version or branch, vulnerability type,
reproduction steps, proof-of-concept code when available, and an impact
assessment. Detailed reports help NVIDIA evaluate and address issues faster.

NVIDIA's Product Security Incident Response Team (PSIRT) will acknowledge the
report, validate and assess the issue, develop and test fixes, and publish a
security bulletin when appropriate.

## Supported Versions

Security fixes are applied to the current `main` branch. C++ benchmarks declare
their Holoscan SDK floor in CMake: model benchmarking requires Holoscan 1.0 or
newer, real-time thread benchmarking requires 3.5 or newer, and green-context
benchmarking requires 3.6 or newer. The repository README's standalone build
example uses Holoscan SDK 3.5 or newer.

## Security Architecture and Context

Holoscan Benchmarks is a set of benchmark applications, measurement helpers, and
published results for the NVIDIA Holoscan SDK. Workloads live under
`benchmarks/`. Reusable instrumentation and log analysis live under
`benchmark_tools/flow_benchmarking/`. Published plots live under
`benchmarks/release_benchmarking/release/`.

This project operates at the benchmark-application and local CLI-tool level. Its
primary security responsibility is to keep measurement runs, patched application
sources, flow logs, and result files inside the directories and devices the
operator selected. It does not authenticate users, expose a network service, or
ship a packaged runtime.

The principal security boundaries are:

- `benchmark.py` launches a HoloHub application. With no `--run-command` it
  builds `./holohub run <application>`; with `--run-command` it passes that
  string to `subprocess.run` with `shell=True`. It also selects GPUs through
  `CUDA_VISIBLE_DEVICES` and, when `--monitor_gpu` is set, samples utilization
  with `nvitop`.
- `patch_application.sh` and `patch_python_sources.py` rewrite C++ and Python
  sources under a caller-supplied directory, inserting `benchmark.hpp` or
  `BenchmarkedApplication` and leaving `.bak` copies beside the originals.
  `benchmark.py` chooses those directories from HoloHub project metadata.
- `benchmark.hpp` and `benchmarked_application.py` read
  `HOLOSCAN_NUM_SOURCE_MESSAGES`, `HOLOSCAN_SCHEDULER`, worker-thread counts,
  and `HOLOSCAN_FLOW_TRACKING_LOG_FILE`, then enable Holoscan flow logging.
- `log_parser.py` and `analyze.py` read those logs from paths given on the
  command line and write CSV and plot files in the working directory.
- `realtime_thread_benchmark` requests `SCHED_DEADLINE`, `SCHED_FIFO`, or
  `SCHED_RR` through Holoscan `add_realtime`, pins a CPU, and can set FIFO
  priority 99. Its README runs the container `--as-root` with Docker
  `--privileged`. It writes JSON under `--output` (default
  `/tmp/benchmark_plots/realtime_thread_benchmark_results.json`) and launches
  `plot_results.py` with `posix_spawnp`.
- `green_context_benchmark` links CUDA, CUPTI, and CCCL. `cupti_profiler.hpp`
  subscribes to CUPTI runtime callbacks and kernel activity. The benchmark
  README runs that container as root.
- `model_benchmarking` opens a caller-supplied data directory and model file
  (default ONNX under the ultrasound-segmentation data path), loads
  `model_benchmarking.yaml` (default V4L2 device `/dev/video6`, TensorRT
  backend), and captures with `V4L2VideoCaptureOp`.
- `benchmarks/release_benchmarking/Dockerfile` extends `ARG BASE_IMAGE` (a
  Holoscan NGC image in the documented workflow), copies the HoloHub launcher
  from the build context, and installs apt packages plus
  `benchmark_tools/flow_benchmarking/requirements.txt` and `jinja2-cli`.
- GitHub Actions (`.github/workflows/ci.yml`) checks out the repo with
  `persist-credentials: false` and `contents: read`, then runs syntax checks
  and log-parser unit tests. That job does not install the requirements file.

### Threat Model

1. **Privileged real-time benchmark container:** `realtime_thread_benchmark.cpp`
   calls `add_realtime` for `SCHED_DEADLINE`, `SCHED_FIFO`, or `SCHED_RR` and
   documents Docker `--privileged` plus `--as-root`, which grants
   `CAP_SYS_NICE` and `CAP_SYS_ADMIN`. A container started that way can change
   host scheduling and is not limited to the benchmark process.
2. **Command execution from `--run-command` and HoloHub metadata:**
   `benchmark.py` `run_command` invokes `subprocess.run(..., shell=True)`. The
   default command interpolates `--holohub-application` and `--language`.
   `--run-command` replaces it with an arbitrary shell string, and the child
   inherits the benchmark environment, including `CUDA_VISIBLE_DEVICES`.
3. **Source rewriting outside this repository:** `patch_python_sources.py`
   walks a directory and rewrites every `.py` file, and `patch_application.sh`
   runs `sed` on every `.cpp` file that declares `holoscan::Application`.
   `benchmark.py` selects those directories from `holoscan-cli` project
   metadata and `holohub_root`. A metadata path or directory argument that
   points at an unintended tree modifies that tree in place.
4. **Caller-selected devices, models, and flow logs:** `model_benchmarking`
   loads the YAML path, `--data` directory, and `--model-name` the operator
   passes, and opens the V4L2 device named in that YAML. `log_parser.py` reads
   a log path and converts timestamp fields with `int` without a size limit.
   Those inputs are trusted local paths; a substituted device node, model
   file, or log can consume GPU time, device access, or parser memory inside
   the benchmark process.
5. **GPU profiling and process inspection:** `cupti_profiler.hpp` enables CUPTI
   runtime and concurrent-kernel activity in-process. `benchmark.py` queries
   NVML through `nvitop.Device` for `--gpu` UUIDs or `Device.all()`. The green
   context README runs the container as root. Profiling and NVML queries use
   whatever GPU access that user or container already has.
6. **Unpinned image-build inputs:** The release-benchmark Dockerfile installs
   `requirements.txt` (only `PyGObject` is pinned) and `jinja2-cli>=0.8.2`
   with pip, and installs apt packages including GTK, Graphviz, pandoc, and
   TeX Live, with no checksums. `BASE_IMAGE` is supplied at build time. A
   substituted base image, index, or package version becomes part of the local
   `holohub:release_benchmarking` image before benchmarks run.

### Critical Security Assumptions

- The operator controls the host, container runtime, and Docker flags. This
  repository does not restrict `--privileged`, `--as-root`, device nodes, or
  GPU access.
- The Holoscan SDK, CUDA, CUPTI, CCCL, and the NGC base image behave as trusted
  platform software and enforce their own device and memory contracts.
- Application names, `--run-command`, patch directories, model and data paths,
  V4L2 device nodes, YAML files, environment variables, and flow logs are
  operator configuration, not untrusted network input.
- Flow-log parsers assume the Holoscan flow-tracking line format. They do not
  authenticate the log producer.
- HoloHub metadata returned by `holoscan-cli` names source and build directories
  the operator intends to patch.
- The benchmark tools do not listen on the network. Any network use is inside
  the Holoscan application or base image under test.
- Secrets are supplied by the deployment environment and are not committed to
  this repository. CI does not persist checkout credentials.
- Third-party Python and apt packages are installed by the operator or by a
  local image build. They are not vendored in this source tree.

## Dependency and Distribution Security

This repository redistributes NVIDIA Apache-2.0 benchmark source and published
result plots. It does not vendor third-party source trees. Analysis and
container workflows install third-party packages at build or run time,
including copyleft components (`nvitop` as published on PyPI, `xdot`,
`PyGObject`, and apt packages such as pandoc). New or upgraded third-party
dependencies must have their license and redistribution terms reviewed before
they are pinned, installed into a published image, or shipped. Components
distributed with a Holoscan product must follow the applicable NVIDIA Open
Source Review Board process. There is no `NOTICE` file in this repository.
