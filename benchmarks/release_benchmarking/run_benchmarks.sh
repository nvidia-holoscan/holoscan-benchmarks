#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
set -e

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
TOP=$(realpath "${SCRIPT_DIR}/../..")
FLOW_BENCHMARKING_DIR=${TOP}/benchmark_tools/flow_benchmarking

run_command() {
    local status=0
    local cmd="$*"

    if [ "${DO_DRY_RUN}" != "true" ]; then
        echo -e "${YELLOW}[command]${NOCOLOR} ${cmd}"
    else
        echo -e "${YELLOW}[dryrun]${NOCOLOR} ${cmd}"
    fi

    [ "$(echo -n "$@")" = "" ] && return 1 # return 1 if there is no command available

    if [ "${DO_DRY_RUN}" != "true" ]; then
        eval "$@"
        status=$?
    fi
    return $status
}

print_platform_details() {
    echo "Platform details:"

    cpu_details=$(lscpu)
    echo "\"cpu\": \"$(echo "$cpu_details" | grep "Model name" | cut -d':' -f2 | xargs)\","

    echo "\"dgpu\": \"$(nvidia-smi --query-gpu=gpu_name --format=csv,noheader | xargs)\","
    echo "\"driver\": \"$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | xargs)\","
    echo "\"cuda\": \"$(nvidia-smi | grep "CUDA Version" | awk '{print $9}')\","

    echo "\"os\": \"$(cat /etc/os-release | grep "PRETTY_NAME" | cut -d'"' -f2)\","
}

plot_benchmark() {
    ARGS=("$@")
    local statistics_args="--max --avg --stddev --median --min --tail --flatness -p 90 95 99 99.9"
    local log_pattern=""
    local log_groups=""
    local log_dir="${SCRIPT_DIR}"

    for i in "${!ARGS[@]}"; do
        arg="${ARGS[i]}"
        if [[ $skipnext == "1" ]]; then
            skipnext=0
        elif [[ "$arg" == "--help" ]]; then
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --log_dir <str>     parent directory containing log \"output\" subdirectory"
            echo "  --log_pattern <str> log pattern to search for"
            echo "  --stats <str>       statistics arguments for analyze.py"
            echo "  --help              Display this help message"
            exit 0
        elif [ "$arg" = "--log_pattern" ]; then
            log_pattern="${ARGS[i + 1]}"
            skipnext=1
        elif [ "$arg" = "--log_dir" ]; then
            log_dir="${ARGS[i + 1]}"
            skipnext=1
        elif [ "$arg" = "--stats" ]; then
            statistics_args="${ARGS[i + 1]}"
            skipnext=1
        fi
    done

    if [[ -z "${log_pattern}" ]]; then
        echo "No log pattern specified with '--log_pattern'"
        exit 1
    fi
    app_name=$(echo "$log_pattern" | sed -E 's/_[0-9].*//')

    counter=1
    for log_directory in $(find ${log_dir}/output -name ${log_pattern} -type d | sort -d); do
        log_groups+="-g "
        for log_file in $(find ${log_directory} -name "logger_*"); do
            log_groups+="$(realpath ${log_file}) "
        done
        log_groups+="Group${counter} "
        counter=$((counter + 1))
    done
    if [[ -z "${log_groups}" ]]; then
        echo "No logs found for pattern ${log_pattern}"
        exit 1
    fi

    processing_dir="$(realpath ${log_dir})/processed/${log_pattern}"
    mkdir -p ${processing_dir}

    pushd ${processing_dir}
    run_command python \
        ${FLOW_BENCHMARKING_DIR}/analyze.py \
        --save-csv \
        --no-display-graphs \
        ${statistics_args} \
        ${log_groups}

    for statistics_csv in $(find ${processing_dir} -name "*.csv"); do
        run_command python \
            ${FLOW_BENCHMARKING_DIR}/generate_bar_graph.py \
            ${statistics_csv} \
            --app "${app_name}" \
            --title "${app_name}" \
            --quiet
    done
    popd
}

main() {
    ARGS=("$@")
    local process_only=false
    local data_dirs=()

    for i in "${!ARGS[@]}"; do
        arg="${ARGS[i]}"
        if [[ $skipnext == "1" ]]; then
            skipnext=0;
        elif [[ "$arg" == "--help" ]]; then
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --dryrun             Print commands without running them"
            echo "  --print              Print platform details"
            echo "  --process <path(s)>  Process prior output without running new benchmarks. Multiple --process values can be specified."
            exit 0;
        elif [[ "$arg" == "--dryrun" ]]; then
            DO_DRY_RUN="true";
        elif [[ "$arg" == "--print" ]]; then
            set +x
            print_platform_details
            exit 0;
        elif [[ "$arg" == "--process" ]]; then
            data_dirs+=("${ARGS[i + 1]}")
            process_only=true
            skipnext=1;
        fi
    done

    if [[ -z "${data_dirs}" ]]; then
        data_dirs=("${SCRIPT_DIR}")
    fi

    if [[ ${process_only} = "false" ]]; then
        echo "SDK 1–4 automatic collection has been retired." >&2
        echo "For SDK 5, use benchmark_tools/flow_benchmarking/benchmark.py --run-command with an instrumented application." >&2
        echo "To process historical results, pass --process <directory>." >&2
        return 2
    fi

    for data_dir in ${data_dirs[@]}; do
        for pattern_suffix in "display_realtime" "display_offline" "headless_offline"; do
            plot_benchmark \
                --log_pattern "endoscopy_tool_tracking_3_[0-9]_1000_greedy_$pattern_suffix" \
                --log_dir ${data_dir}
        done

        for pattern_suffix in "display_realtime" "headless_offline"; do
            plot_benchmark \
                --log_pattern "multiai_ultrasound_3_[0-9]_1000_greedy_$pattern_suffix" \
                --log_dir ${data_dir}
        done

        # Process long-running benchmarks
        for pattern_suffix in "display_realtime"; do
            plot_benchmark \
                --log_pattern "long_running_endoscopy_tool_tracking_3_[0-9]_greedy_$pattern_suffix" \
                --log_dir ${data_dir}
        done
    done
}

main "$@"
