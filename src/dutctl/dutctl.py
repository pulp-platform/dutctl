# Copyright 2025 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Paul Scheffler <paulsc@iis.ee.ethz.ch>
# Thomas Benz <tbenz@iis.ee.ethz.ch>

# dutctl: control a device under test and its instruments remotely.

import os
import time
import argparse
import pathlib
import functools
import asyncio
import pyvisa as vs

from dutctl import aginstr
from dutctl import dut


TOOL_NAME = 'dutctl'
DEF_BAUD = 115200

ACTIONS = ('reset', 'cycle', 'leak', 'measure', 'run', 'poweroff')
OCD_ACTIONS = ('reset', 'cycle', 'run')

DEF_GDB = 'riscv64-unknown-elf-gdb'
DEF_OCD = 'openocd'


# Global event to terminate program
end_event = asyncio.Event()


def parse_and_validate_args(args: list) -> argparse.Namespace:
    # Determine default directories
    working_dir = pathlib.Path(os.getcwd()).resolve()
    default_cfg_dir = working_dir / 'common'
    default_log_leaf = f'{TOOL_NAME}_{int(1000*time.time())}'
    default_log_dir = working_dir / 'logs' / default_log_leaf

    # Build pre-parser for meta-arguments, e.g. number of chips and file arguments
    meta_parser = argparse.ArgumentParser(add_help=False)
    meta_parser.add_argument('-n', '--nchips', default=1, type=int)
    meta_parser.add_argument('-f', '--file', type=argparse.FileType('r'))
    meta_args, _ = meta_parser.parse_known_args()
    num_chips = meta_args.nchips
    file_args = []
    if meta_args.file is not None:
        # Strip comments (begin with `#`), then put contents back together and split on whitespace.
        # Note that we do *not* support end-of-line comments.
        file_args_lines = [line for line in meta_args.file.readlines() if not line.startswith('#')]
        file_args = '\n'.join(file_args_lines).strip().split()
        print(f'INFO: read file arguments: `{" ".join(file_args)}`')

    # Build base parser. Add (ignored) meta-args here for help.
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description=f'{TOOL_NAME}: Control a RISC-V-based device under test (DUT) '
        'and its lab instruments remotely.')
    parser.add_argument(
        'action', help=f'One of: {", ".join(ACTIONS)}.')
    parser.add_argument(
        '-n', '--nchips', default=1, type=int,
        help='Number of chips to control; see chip args below. The default is `1`.')
    parser.add_argument(
        '-f', '--file', help='File with command line arguments.')
    parser.add_argument(
        '-i', '--instr', metavar="PSUCFG", default=default_cfg_dir/'instr.yml',
        help='Path to the instrument config file. The default is `<workdir>/config/instr.yml`.')
    parser.add_argument(
        '-l', '--logdir', metavar="DIR", default=default_log_dir,
        help='Directory for logs. Created and used only when OCD is launched. '
        f'The default is a subdirectory of `<workdir>/logs` timestamped in the '
        f'format `{default_log_leaf}`. Measurements are both printed and, '
        f'if triggered through serial output, written to `<logdir>/measure<chip>.json`.')
    parser.add_argument(
        '-t', '--trst', metavar="SECS", default=0.1, type=float,
        help='Reset pulse width. The default is `0.1`.')
    parser.add_argument(
        '-a', '--trafter', metavar="SECS", default=0.1, type=float,
        help='Time to wait after issuing the reset. The default is `0.1`.')
    parser.add_argument(
        '-p', '--tpoll', metavar="SECS", default=0.5, type=float,
        help='Polling period for subprocesses. The default is `0.5`.')
    parser.add_argument(
        '-s', '--tswait', metavar="SECS", default=0.5, type=float,
        help='Time to wait before standby measurement. The default is `0.5`.')
    parser.add_argument(
        '-w', '--tlwait', metavar="SECS", default=0.5, type=float,
        help='Time to wait before leak measurement. The default is `0.5`.')
    parser.add_argument(
        '-r', '--noreconf', action='store_true',
        help='Do not power-cycle or reconfigure instruments.')
    parser.add_argument(
        '-e', '--noreset', action='store_true',
        help='Do not send reset.')
    parser.add_argument(
        '-b', '--ocdbin', metavar="BINARY", default=DEF_OCD,
        help='Binary for OpenOCD. Used only when OCD is launched. '
        f'The default is `{DEF_OCD}`. ')
    parser.add_argument(
        '-d', '--gdbbin', metavar="BINARY", default=DEF_GDB,
        help='Binary for GDB. Used only when GDB is launched. '
        f'The default is `{DEF_GDB}`. ')
    for chip in range(num_chips):
        group = parser.add_argument_group(
            f'Chip {chip}', f'Arguments specific to chip {chip} of the DUT (see `-n` option)')
        # With no file argument, we store whether the flag was passed or not (True/False).
        # We infer from this whether OpenOCD should be run and override the path later.
        group.add_argument(
            f'-o{chip}', f'--ocd{chip}', nargs='?', metavar="OCDCFG",
            help=f'Runs OpenOCD with the passed config file. '
            f'Usable with the actions {", ".join(OCD_ACTIONS)}. '
            f'The default argument is `<workdir>/common/chip{chip}.ocd`. '
            f'OpenOCD output is logged to `<logdir>/ocd{chip}.log.` '
            f'Terminates {TOOL_NAME} if and when OpenOCD does.',
            const=True, default=False)
        group.add_argument(
            f'-g{chip}', f'--gdb{chip}', nargs='?', metavar="GDBSCRIPT",
            help=f'Runs GDB with the passed script. Usable only with the action run. '
            f'Implies `--ocd{chip}` with its default argument if not passed. '
            f'GDB output is logged to `<logdir>/gdb{chip}.log.` '
            f'Terminates {TOOL_NAME} if and when GDB or OpenOCD do.')
        group.add_argument(
            f'-u{chip}', f'--uart{chip}', nargs='?', metavar="UARTDEV[:BAUDRATE]",
            help=f'Observe the output of the passed serial device (default baudrate {DEF_BAUD}) '
            f'and log it to `<logdir>/uart{chip}.log`. Usable only with the action run. If passed,'
            f' the received output can trigger PSU measurements with control lines of the format '
            f'`@{TOOL_NAME}:psumeas:<key>:<delay_ms>[:<supply>[:<channel>]]`. It can also add '
            f' computed results to the measurement JSON with control lines of the format '
            f'`@{TOOL_NAME}:dutmeas:<key>:<result_string>`.'
            f' The control lines take effect when their trailing newline (`\\n`) is received.')

    # Parse arguments
    args = parser.parse_args(args + file_args)

    # Check arguments
    if args.action not in ACTIONS:
        parser.error(f'action must be one of: {", ".join(ACTIONS)}.')
    if args.action == 'run':
        if all((vars(args)[f'gdb{d}'] is None) for d in range(num_chips)):
            parser.error('action run requires OpenOCD and GDB scripts for at least one chip.')
    else:
        if any((vars(args)[f'gdb{d}'] is not None
                or vars(args)[f'uart{d}'] is not None) for d in range(num_chips)):
            parser.error('GDB or UART output observation require action run.')
    if args.action not in OCD_ACTIONS and any(
            (vars(args)[f'ocd{d}'] is not False) for d in range(num_chips)):
        parser.error(f'Launching OpenOCD requires one of the actions {", ".join(OCD_ACTIONS)}.')

    # Extend default args as necessary, check that needed files exist
    must_exist_files = [args.instr]
    for d in range(num_chips):
        # If --ocd{d} is implicit through --gdb{d} or explicit without arg: set default file.
        if (vars(args)[f'gdb{d}'] is not None and vars(args)[f'ocd{d}'] is False) \
                or vars(args)[f'ocd{d}'] is True:
            vars(args)[f'ocd{d}'] = default_cfg_dir/f'chip{d}.ocd'
            must_exist_files.append(vars(args)[f'ocd{d}'])
        # No file passed and none required: pass on None to signal that OCD shall not be launched.
        elif vars(args)[f'ocd{d}'] in (True, False):
            vars(args)[f'ocd{d}'] = None
        # A file is explicitly passed: do not override it and check its existence.
        else:
            must_exist_files.append(vars(args)[f'ocd{d}'])
        # Any GDB file that is passed must exist. Otherwise, it is None and GDB is not launched.
        if vars(args)[f'gdb{d}'] is not None:
            must_exist_files.append(vars(args)[f'gdb{d}'])
    for f in must_exist_files:
        if not pathlib.Path(f).is_file():
            parser.error(f'File `{f}` does not exist')

    # Split UART args into path and baudrate
    for d in range(num_chips):
        vars(args)[f'baud{d}'] = DEF_BAUD
        if vars(args)[f'uart{d}'] is not None and ':' in vars(args)[f'uart{d}']:
            vars(args)[f'uart{d}'], vars(args)[f'baud{d}'] = vars(args)[f'uart{d}'].split(':')

    # Return arguments
    return args


async def main(args: list) -> int:
    # Parse and validate args
    args = parse_and_validate_args(args)

    # Load PSU configs and connect to them
    instr_cfg = aginstr.config_from_yml(args.instr)
    rm = vs.ResourceManager()
    psu_instrs = aginstr.connect_instrs(rm, instr_cfg['supplies'])
    siggen_instrs = aginstr.connect_instrs(rm, instr_cfg['siggens'])
    psu_cfgs = instr_cfg['supplies']
    psus_ganged = instr_cfg['supplies']
    siggen_cfgs = instr_cfg['siggens']

    print('INFO: connected to instruments')

    # Handle supply management
    if args.action == 'reset':
        aginstr.reconf_siggens(siggen_instrs, siggen_cfgs)
        aginstr.reset(psu_instrs, psu_cfgs, args.trst)
    elif args.action == 'poweroff':
        aginstr.siggens_off(siggen_instrs, siggen_cfgs)
        aginstr.power_off(psu_instrs, psu_cfgs, psus_ganged)
    elif args.action in ('cycle', 'run', 'leak'):
        if not args.noreconf:
            aginstr.siggens_off(siggen_instrs, siggen_cfgs)
            aginstr.power_reset_cycle(psu_instrs, psu_cfgs, psus_ganged, args.trst)
            time.sleep(args.tswait)
            await dut.async_meas(psu_instrs, psu_cfgs, name='_standby')
            aginstr.reconf_siggens(siggen_instrs, siggen_cfgs)
        if not args.noreset:
            aginstr.reset(psu_instrs, psu_cfgs, args.trst)
    elif args.action == 'measure':
        await dut.async_meas(psu_instrs, psu_cfgs)
    else:
        raise ValueError(f'Unexpected action: {args.action}')

    if not args.action == 'measure':
        time.sleep(args.trafter)
        print('INFO: instrument control complete')

    if args.action == 'leak':
        print('INFO: Disabling chosen siggens for leakage measurement')
        aginstr.siggens_off(siggen_instrs, siggen_cfgs)
        time.sleep(args.tlwait)
        await dut.async_meas(psu_instrs, psu_cfgs, name='_leak')

    # Handle asynchronous tasks
    loop = asyncio.get_event_loop()
    tasks = {}
    log_dir = pathlib.Path(args.logdir)
    if args.action in ('reset', 'cycle', 'run'):
        # Launch OCD as needed
        for d in range(args.nchips):
            if vars(args)[f'ocd{d}'] is not None:
                ocd_path = log_dir / f'ocd{d}.log'
                tasks[f'ocd{d}'] = loop.create_task(dut.handle_ocd(
                    end_event, args.ocdbin, vars(args)[f'ocd{d}'], ocd_path, args.tpoll))
    if args.action == 'run':
        for d in range(args.nchips):
            # Launch UART as needed
            if vars(args)[f'uart{d}'] is not None:
                meas_path = log_dir / f'measure{d}.json'
                out_path = log_dir / f'uart{d}.log'
                tasks[f'uart{d}'] = loop.create_task(dut.handle_uart(
                   end_event, vars(args)[f'uart{d}'], meas_path, out_path, psu_instrs,
                   psu_cfgs, vars(args)[f'baud{d}'], args.tpoll, TOOL_NAME))
            # Launch GDB as needed
            if vars(args)[f'gdb{d}'] is not None:
                gdb_path = log_dir / f'gdb{d}.log'
                tasks[f'gdb{d}'] = loop.create_task(dut.handle_gdb(
                    end_event, args.gdbbin, vars(args)[f'gdb{d}'], gdb_path, args.tpoll))

    # Collect asynchronous tasks, OR returns
    results = (await asyncio.gather(*tasks.values())) if len(tasks) else []
    res_dict = dict(zip(tasks.keys(), results))
    if len(res_dict):
        print(f'INFO: subprocess return codes: {res_dict}')
    return functools.reduce(lambda a, b: a or b, results, 0)
