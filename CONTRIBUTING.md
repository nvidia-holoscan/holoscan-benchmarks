# Contributing

Contributions can add validated Holoscan SDK 5.x benchmark workloads, improve shared
tooling, or correct documentation. Holoscan SDK 5.0.0 is the baseline.

## Where changes belong

- Put each new application or operator benchmark in its own directory under
  `benchmarks/`. Keep its workload, configuration, specialized helpers, and
  measurement procedure together.
- Put reusable execution, instrumentation, and analysis tools under
  `benchmark_tools/`. Extend the existing flow tools when they fit the task.
- Keep CI workflows and their repository checks under `.github/`.

Other contributions have a different home:

- Applications go to Holoscan Applications (`nvidia-holoscan/holoscan-applications`).
- Tutorials go to Holoscan Tutorials (`nvidia-holoscan/holoscan-tutorials`).
- Reusable operators and Holoscan Modules go to
  their own project repositories. See the [Create a Module tutorial](https://github.com/nvidia-holoscan/holoscan-tutorials/tree/main/tutorials/holoscan-modules/create-a-module).
- Holoscan CLI changes go to [Holoscan CLI](https://github.com/nvidia-holoscan/holoscan-cli).
- Holoscan SDK bugs and feature requests go to the
  [Holoscan SDK](https://github.com/nvidia-holoscan/holoscan-sdk/issues).

## Add or update a benchmark

Start with the [benchmark directory overview](benchmarks/README.md) and
[flow benchmarking guide](benchmark_tools/flow_benchmarking/README.md#benchmark-your-own-application).
You can use the tools on your own application before contributing it here.

Include a README that explains:

1. What is measured, the metric units, and the workload or operator configuration.
2. Required hardware, Holoscan SDK and software versions, permissions, models, and input
   data, including how to obtain external dependencies.
3. Exact build and run commands, their working directory, and where outputs go.
4. How measurements are collected and analyzed, including warm-up exclusions,
   sample counts, repetitions, and any instrumentation overhead.
5. How to interpret the results and reproduce the reported configuration.

Use functionality present in Holoscan SDK 5.x or Holoscan Applications. If the application
source lives elsewhere, identify its repository and tested revision. Include
hardware and software details with measurements. Build and run the benchmark
and verify that its measurements are valid before registering it in
`benchmarks/CMakeLists.txt`. Document the workload in its own README.
Remove unsupported or unverified legacy workloads. Keep temporary logs and
build outputs out of the contribution.

## Change shared tools

Keep commands usable from the documented working directories. Update affected
imports, scripts, Docker references, documentation, and CI when moving files.
Preserve the meaning and units of measurements; explain any intentional changes
to results or command-line behavior.

For behavior changes, add focused coverage to the relevant tests. Flow-log
parser tests live in `benchmark_tools/flow_benchmarking/tests/` and run without
the Holoscan SDK or a GPU.

## Validate and submit

From the repository root with Python 3.10+ and Bash:

```bash
python3 .github/scripts/check.py
python3 -m unittest discover -s benchmark_tools/flow_benchmarking/tests -v
```

These checks validate Python, JSON, and shell syntax and test flow-log parsing.
For changes to benchmark execution or measurements, also build and run the
affected benchmark in its required environment. CI does not validate GPU
execution or performance.

Open a pull request describing the change and the checks you ran. For runtime
or result changes, include the tested hardware, Holoscan SDK version, application
revision, and commands. State which checks could not be run. A pull request is
accepted once CI passes and a Holoscan maintainer approves it.

## Security-sensitive steps

If a benchmark runs containers as root or privileged, changes host devices or kernel
settings, opens network ports, or downloads files without checksums, say so in its
README before the step. Then add the risk to the threat model in
[SECURITY.md](SECURITY.md).

## Signing your contribution

Every commit must carry a `Signed-off-by` trailer, added by `git commit -s`. Signing off
certifies the [Developer Certificate of Origin](https://developercertificate.org/): you
wrote the contribution, or otherwise have the right to submit it under the
[Apache-2.0 license](LICENSE). Pull requests with unsigned commits are not accepted.

To report a security vulnerability, follow [SECURITY.md](SECURITY.md) instead of opening a
public issue.
