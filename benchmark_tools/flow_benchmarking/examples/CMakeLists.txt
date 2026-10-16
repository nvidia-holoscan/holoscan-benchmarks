# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 4.0)
project(holoscan_flow_tracking LANGUAGES CXX)
find_package(holoscan 5.0 REQUIRED CONFIG COMPONENTS core)
find_package(Threads REQUIRED)
add_executable(flow_tracking flow_tracking.cpp)
target_compile_features(flow_tracking PRIVATE cxx_std_20)
target_include_directories(flow_tracking PRIVATE ..)
target_link_libraries(flow_tracking PRIVATE holoscan::core Threads::Threads)

add_executable(tensor_flow_tracking tensor_flow_tracking.cpp)
target_compile_features(tensor_flow_tracking PRIVATE cxx_std_20)
target_include_directories(tensor_flow_tracking PRIVATE ..)
target_link_libraries(tensor_flow_tracking PRIVATE holoscan::core Threads::Threads)
