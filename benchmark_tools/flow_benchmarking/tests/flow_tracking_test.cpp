// SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
#include "flow_tracking.hpp"
#include <cassert>
#include <locale>
#include <stdexcept>

struct GroupedNumbers : std::numpunct<char> {
  char do_thousands_sep() const override { return ','; }
  std::string do_grouping() const override { return "\3"; }
};

int main(int argc, char** argv) {
  assert(argc == 2);
  using namespace holoscan_benchmark;
  FlowTrace root{42};
  root.append("source", 1000000, 2000000);
  auto left = root;
  auto right = root;
  left.append("left", 3000000, 4000000);
  right.append("right", 4000000, 6000000);
  // Applications may change the global locale. JSON numbers must not inherit
  // grouping separators from it (this is independent of installed locales).
  std::locale::global(std::locale{std::locale::classic(), new GroupedNumbers});
  FlowLogger logger{argv[1]};
  logger.write(left);
  logger.write(right);
  bool rejected = false;
  try { right.append("bad", 1, 0); } catch (const std::invalid_argument&) { rejected = true; }
  assert(rejected);
  logger.close();
  rejected = false;
  try { logger.write(root); } catch (const std::runtime_error&) { rejected = true; }
  assert(rejected);
}
