# Copyright 2025 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Paul Scheffler <paulsc@iis.ee.ethz.ch>
# Thomas Benz <tbenz@iis.ee.ethz.ch>
# Gianna Paulin <pauling@iis.ee.ethz.ch>

# Common OpenOCD configuration for RISC-V SoCs.

adapter driver ftdi

ftdi vid_pid 0x0403 0x6014
ftdi channel 0
ftdi layout_init 0x00e8 0x60eb
reset_config none

set _CHIPNAME riscv
jtag newtap $_CHIPNAME cpu -irlen 5 -expected-id 0x20002001

set _TARGETNAME $_CHIPNAME.cpu
target create $_TARGETNAME riscv -chain-position $_TARGETNAME -coreid 0

gdb_report_data_abort enable
gdb_report_register_access_error enable

riscv set_reset_timeout_sec 120
riscv set_command_timeout_sec 120

# prefer to use sba for system bus access
riscv set_mem_access sysbus progbuf abstract

# Try enabling address translation (only works for newer versions)
if { [catch {riscv set_enable_virtual on} ] } {
    echo "Warning: This version of OpenOCD does not support address translation. To debug on virtual addresses, please update to the latest version." }

init
halt
echo "Ready for Remote Connections"
