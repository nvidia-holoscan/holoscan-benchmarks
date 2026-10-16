# SPDX-FileCopyrightText: Copyright (c) 2023-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Run already instrumented SDK 5 applications without rewriting their sources."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import threading
import time

from log_parser import parse_log_as_paths_latencies


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def terminate_group(process):
    """Escalate against the group even if its shell leader exits first."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        process.poll()  # reap the shell without confusing it with its descendants
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.02)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def run_command(command, env, output, timeout, cancelled):
    # Keep output on disk: long application runs must not fill the runner's RAM.
    with output.open("x", encoding="utf-8") as stream:
        process = subprocess.Popen(command, shell=True, env=env, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while True:
                if cancelled.is_set():
                    raise RuntimeError(f"application cancelled; see {output}")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    code = process.wait(timeout=min(0.1, remaining))
                    break
                except subprocess.TimeoutExpired:
                    pass
        except BaseException:
            terminate_group(process)
            raise
    if code:
        terminate_group(process)
        raise RuntimeError(f"application exited with code {code}; see {output}")
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return
    # A launcher must join its workers before reporting completion. Otherwise a
    # later trial could overlap unfinished work or parse a log still being written.
    terminate_group(process)
    raise RuntimeError(f"application left background processes running; see {output}")


def monitor_gpu(devices, output, stop):
    with output.open("x", encoding="utf-8") as stream:
        while not stop.is_set():
            values = [device.gpu_utilization() for device in devices]
            if any(not isinstance(value, (int, float)) for value in values):
                raise RuntimeError("GPU utilization is unavailable on this device")
            stream.write(str(sum(values) / len(values)) + ",")
            stream.flush()
            stop.wait(1)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-command", required=True, help="instrumented application shell command")
    parser.add_argument("-r", "--runs", type=positive_int, default=1)
    parser.add_argument("-i", "--instances", type=positive_int, default=1)
    parser.add_argument("-m", "--num_messages", type=positive_int, default=100,
                        help="HOLOSCAN_NUM_SOURCE_MESSAGES; application must honor this limit")
    parser.add_argument("-d", "--log-directory", type=Path,
                        default=Path(time.strftime("flow-results-%Y%m%d-%H%M%S")))
    parser.add_argument("--timeout", type=positive_int, default=120,
                        help="maximum seconds per application instance (default: 120)")
    parser.add_argument("-g", "--gpu", default="all", help="CUDA_VISIBLE_DEVICES value")
    parser.add_argument("-u", "--monitor_gpu", action="store_true",
                        help="sample physical GPU utilization with optional nvitop")
    args = parser.parse_args(argv)
    devices = []
    if args.monitor_gpu:
        from nvitop import Device
        devices = (Device.all() if args.gpu == "all" else
                   [Device(index=int(g)) if g.isdigit() else Device(uuid=g)
                    for g in args.gpu.split(",")])
        if not devices:
            parser.error("no GPUs available for monitoring")
    output = args.log_directory.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Refuse existing trial artifacts so stale logs can never make a failed run pass.
    with (output / "benchmark.json").open("x", encoding="utf-8") as stream:
        json.dump({"command": args.run_command, "runs": args.runs, "instances": args.instances,
                   "messages": args.num_messages, "timeout": args.timeout,
                   "gpu": args.gpu, "cwd": os.getcwd()}, stream, indent=2)
    env = os.environ.copy()
    env["HOLOSCAN_NUM_SOURCE_MESSAGES"] = str(args.num_messages)
    if args.gpu != "all":
        env["CUDA_VISIBLE_DEVICES"] = args.gpu
    failures = []
    for run in range(1, args.runs + 1):
        stop = threading.Event()
        cancelled = threading.Event()
        with ThreadPoolExecutor(max_workers=args.instances + 1) as pool:
            monitor = (pool.submit(monitor_gpu, devices, output / f"gpu_utilization_{run}.csv", stop)
                       if devices else None)
            futures = []
            try:
                for instance in range(1, args.instances + 1):
                    trace = output / f"flow_{run}_{instance}.jsonl"
                    console = output / f"console_{run}_{instance}.log"
                    if trace.exists() or console.exists():
                        raise FileExistsError(f"trial artifacts already exist: {trace}")
                    child_env = dict(env, HOLOSCAN_FLOW_TRACKING_LOG_FILE=str(trace))
                    future = pool.submit(run_command, args.run_command, child_env, console, args.timeout, cancelled)
                    futures.append((future, trace))
                for future, trace in futures:
                    try:
                        future.result()
                        if not any(parse_log_as_paths_latencies(trace).values()):
                            raise RuntimeError(f"no flow records collected in {trace}")
                    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
                        failures.append(str(error))
            except BaseException:
                cancelled.set()
                raise
            finally:
                stop.set()
                if monitor:
                    monitor.result()
        if failures:
            break
    if failures:
        raise RuntimeError("\n".join(failures))
    print(f"Collected {args.runs * args.instances} flow logs in {output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("Benchmark cancelled", file=sys.stderr)
        sys.exit(130)
    except (OSError, RuntimeError, ValueError, ImportError) as error:
        print(f"Benchmark failed: {error}", file=sys.stderr)
        sys.exit(1)
