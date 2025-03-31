# Copyright 2025 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Paul Scheffler <paulsc@iis.ee.ethz.ch>
# Thomas Benz <tbenz@iis.ee.ethz.ch>

target extended-remote localhost:3333

# Load binary
load helloworld/helloworld.spm.elf

# Launch binary
continue

# Read scratch reg 2
x/d 0x03000008

# Exit from GDB
exit
