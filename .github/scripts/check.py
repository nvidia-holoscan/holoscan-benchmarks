# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Check portable source and metadata syntax without runtime dependencies."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRS = ("benchmarks", "benchmark_tools", ".github/scripts")

python_files = [
    path
    for directory in SOURCE_DIRS
    for path in sorted((ROOT / directory).rglob("*.py"))
]
for path in python_files:
    compile(path.read_bytes(), str(path), "exec")

json_files = [
    path
    for directory in SOURCE_DIRS
    for path in sorted((ROOT / directory).rglob("*.json"))
]
for path in json_files:
    json.loads(path.read_text(encoding="utf-8"))

shell_files = [
    path
    for directory in SOURCE_DIRS
    for path in sorted((ROOT / directory).rglob("*.sh"))
]
for path in shell_files:
    subprocess.run(["bash", "-n", str(path)], check=True)

print(
    f"Validated {len(python_files)} Python files, {len(json_files)} JSON files, "
    f"and {len(shell_files)} shell scripts."
)
