# Contributing

Contributions can add benchmark workloads, improve shared tooling, correct
documentation, or publish reproducible results.

## Where changes belong

- Put each new application or operator benchmark in its own directory under
  `benchmarks/`. Keep its workload, configuration, specialized helpers, and
  measurement procedure together.
- Put reusable execution, instrumentation, and analysis tools under
  `benchmark_tools/`. Extend the existing flow tools when they fit the task.
- Keep release scenarios and reports in `benchmarks/release_benchmarking/`.
  The release suite currently includes Endoscopy Tool Tracking and Multi-AI
  Ultrasound scenarios.
- Keep CI workflows and their repository checks under `.github/`.

## Add or update a benchmark

Start with the [benchmark catalog](benchmarks/README.md) and
[flow benchmarking guide](benchmark_tools/flow_benchmarking/README.md#benchmark-your-own-application).
You can use the tools on your own application before contributing it here.

Include a README that explains:

1. What is measured, the metric units, and the workload or operator configuration.
2. Required hardware, SDK and software versions, permissions, models, and input
   data, including how to obtain external dependencies.
3. Exact build and run commands, their working directory, and where outputs go.
4. How measurements are collected and analyzed, including warm-up exclusions,
   sample counts, repetitions, and any instrumentation overhead.
5. How to interpret the results and reproduce the reported configuration.

If the application source lives elsewhere, identify its repository and tested
revision. Include hardware and software details with published measurements.
Follow neighboring projects' `metadata.json` format when supplying project
metadata, and add the benchmark to the catalog. Keep temporary logs and build
outputs out of the contribution.

## Change shared tools

Keep commands usable from the documented working directories. Update affected
imports, scripts, Docker references, documentation, and CI when moving files.
Preserve the meaning and units of measurements; explain any intentional changes
to results or command-line behavior.

For behavior changes, add focused coverage to the relevant tests. Flow-log
parser tests live in `benchmark_tools/flow_benchmarking/tests/` and run without
the SDK or a GPU.

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
or result changes, include the tested hardware, SDK version, application
revision, and commands. State which checks could not be run.
