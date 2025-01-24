# Copyright 2025 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Paul Scheffler <paulsc@iis.ee.ethz.ch>
# Thomas Benz <tbenz@iis.ee.ethz.ch>
# Gianna Paulin <pauling@iis.ee.ethz.ch>


# OpenOCD configuration for DUT JTAG port 0.

adapter speed  4667
adapter serial 210249B86B4A
gdb_port 3333
tcl_port 6666
telnet_port 4444

source "[file dirname [file normalize [info script]]]/openocd.common.tcl"
