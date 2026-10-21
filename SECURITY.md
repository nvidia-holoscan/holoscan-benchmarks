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

Security fixes are applied to the current `main` branch. The shared measurement
and analysis tools target Holoscan SDK 5.x, using 5.0.0 as the baseline. Their
C++ examples require Holoscan SDK 5.0 or newer. The `benchmarks/` directory currently
contains no runnable workloads; legacy benchmarks and release reports were
removed during the Holoscan SDK 5 compatibility review.

## Security Architecture and Context

Holoscan Benchmarks provides local measurement and analysis tools under
`benchmark_tools/flow_benchmarking/`. Its primary security responsibility is to
keep measurement runs, flow logs, and result files inside the directories the
operator selected. It does not authenticate users, expose a network service,
or ship a packaged runtime.

The principal security boundaries are:

- `benchmark.py` executes the operator's required `--run-command` with
  `subprocess.Popen(..., shell=True)`. It inherits the environment, supplies
  per-instance logging and message-count variables, and optionally selects
  GPUs through `CUDA_VISIBLE_DEVICES`. It does not rewrite application sources.
- The runner creates trial metadata and console files exclusively, checks
  collected flow logs, and terminates application process groups on failure,
  timeout, or cancellation. The application must honor the requested message
  limit and implement its own instrumentation.
- `flow_tracking.hpp` and `flow_tracking.py` write application-provided timing
  records to the selected file. The Holoscan SDK integration examples and correlation
  helper carry measurement provenance through Holoscan SDK 5 graphs.
- `log_parser.py`, `analyze.py`, and plotting tools read caller-selected logs
  and write statistics, CSV, graph, and image files. Analysis accepts Holoscan SDK 5
  JSONL records and legacy flow logs.
- With `--monitor_gpu`, `benchmark.py` samples physical GPU utilization through
  the optional `nvitop` package and NVML.
- GitHub Actions checks source syntax, installs the analysis requirements, and
  runs collection and analysis tests. Checkout uses `persist-credentials: false`
  with `contents: read`. CI does not qualify GPU workloads or performance.

### Threat Model

1. **Operator-supplied shell commands:** `--run-command` is an arbitrary shell
   command and runs with the caller's permissions and inherited environment.
   Application commands must come from a trusted operator.
2. **Caller-selected files:** Flow-log parsers, analysis tools, and record writers
   operate on local paths. Large or malformed input may consume memory or CPU;
   the tools do not authenticate log producers. Some analysis outputs may
   replace existing files at the selected destination.
3. **GPU and process access:** Optional NVML monitoring and Holoscan SDK applications use
   the device access already granted to the invoking user or container. The
   runner can terminate the process groups it starts.

### Critical Security Assumptions

- The operator controls the host, container runtime, application command, device
  access, environment variables, and input/output paths.
- The Holoscan SDK and its runtime dependencies are trusted platform software.
- Applications implement instrumentation correctly; log parsing cannot establish
  that timestamps faithfully represent the workload or that a requested
  message limit was honored.
- The benchmark tools do not listen on the network. Network use belongs to the
  application under test or to dependency installation.
- Secrets are supplied by the deployment environment and are not committed to
  this repository. CI does not persist checkout credentials.
- Third-party packages are installed by the operator or CI and are not vendored
  in this source tree.

## Dependency and Distribution Security

This repository redistributes NVIDIA Apache-2.0 measurement and analysis source.
It does not vendor third-party source trees. Analysis uses NumPy, Matplotlib,
and pydot; GPU monitoring can use `nvitop`, and graph viewing can use Graphviz
or `xdot`. New or upgraded third-party dependencies must have their license and
redistribution terms reviewed before they are pinned, installed into a published
image, or shipped. Components distributed with a Holoscan product must follow
the applicable NVIDIA Open Source Review Board process. There is no `NOTICE`
file in this repository.
