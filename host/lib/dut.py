# Copyright 2025 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Paul Scheffler <paulsc@iis.ee.ethz.ch>
# Thomas Benz <tbenz@iis.ee.ethz.ch>

# Coroutines attaching to, logging, and handling UART commands.

import re
import time
import pathlib
import asyncio
import serial_asyncio
import aiofiles
import signal
import json
from subprocess import PIPE
from ast import literal_eval
from pprint import pprint
from lib import aginstr


# Parse to specific literal (e.g. hex, int, float, list, ...) if possible, otherwise return input.
def literal_or_str(expr: str):
    try:
        return literal_eval(expr)
    except ValueError:
        return expr


# Returns a float is string is float literal or None
def try_float(expr: str) -> float:
    try:
        return float(expr)
    except ValueError:
        return None


def ensure_par_dir_exists(file_path: str):
    path_obj = pathlib.Path(file_path)
    path_obj.parent.mkdir(exist_ok=True, parents=True)


# Spawn and wait on subprocess outputting to file
async def async_subproc(end_event: asyncio.Event, argv: list, out_path: str,
    poll_period : float, sig: int = None, mask_return: int = None) -> int:
    assert(poll_period > 0)
    ensure_par_dir_exists(out_path)
    async with aiofiles.open(out_path, 'w+') as f:
        p = await asyncio.create_subprocess_exec(*argv, stdin=PIPE, stdout=f, stderr=f)
        while p.returncode is None:
            if end_event.is_set():
                if sig is None:
                    p.terminate()
                else:
                    p.send_signal(sig)
                await p.wait()
                assert(p.returncode is not None)
            else:
                await asyncio.sleep(poll_period)
        # If this process is first to terminate: propagate end signal
        if not end_event.is_set():
            end_event.set()
        # Mask return if desired
        if mask_return is not None and p.returncode == mask_return:
            return 0
        else:
            return p.returncode


# =================
#    Measurement
# =================

async def write_out_meas(meas: dict, async_file = None):
    meas_str = json.dumps(meas)
    print('MEAS: ', end='')
    pprint(meas)
    if async_file is not None:
        await async_file.write(meas_str + '\n')


# TODO: File dump should be JSON! fix this
async def async_meas(psu_instrs: dict, psu_configs: dict, async_file = None, name: str = None):
    # We run the TCP-blocking measurement in an executor to be able to await it
    meas_dat = await asyncio.get_running_loop().run_in_executor(
        None, aginstr.meas_vol_cur, psu_instrs, psu_configs)
    await write_out_meas({name: meas_dat}, async_file)


async def parse_psuline(name: str, line: str, line_queue: asyncio.Queue,
        psu_instrs: dict, psu_configs:dict, tname: str) -> (bool, tuple, dict):
    psuline = re.match('@' + tname + ':psu' + name +
        r':([^:]+):(\d+)(?::([^:\r\n]+))?(?::(\d+))?', line)
    if psuline is None or len(psuline.groups()) != 4 or \
            (name == 'ctl' and try_float(psuline.groups()[0]) is None):
        print(f'ERROR: malformed PSU {name} line (ignored): {line}')
        line_queue.task_done()
        return (False, None, None)
    psuline = psuline.groups()
    psu_configs_loc = psu_configs
    # Filter supply for line if specified
    if psuline[2] is not None:
        supply = psuline[2]
        try:
            psu_configs_loc = {supply: psu_configs[supply]}
        except KeyError:
            print(f'ERROR: unknown supply `{supply}` '
                f' in PSU {name} line (ignored): {line}')
            line_queue.task_done()
            return (False, None, None)
        # Filter channel for line if specified
        if psuline[3] is not None:
            cidx = int(psuline[3])
            try:
                psu_configs_loc[supply].channels = \
                    {cidx: psu_configs_loc[supply].channels[cidx]}
                # if control line, edit voltage
                if name == 'ctl':
                    psu_configs_loc[supply].channels[cidx].vol = float(psuline[0])
            except KeyError:
                print(f'ERROR: unknown channel `{cidx}` '
                    f'in PSU {name} line (ignored): {line}')
                line_queue.task_done()
                return (False, None, None)
    # Sleep for specified time before line
    await asyncio.sleep(1e-3 * float(psuline[1]))
    # Let main flow take over from here; don't forget to signal `task_done`!
    return True, psuline, psu_configs_loc


# ==========
#    UART
# ==========

async def uart_handle_control_lines(end_event: asyncio.Event, meas_path: str,
        line_queue: asyncio.Queue, psu_instrs: dict, psu_configs: dict, tname: str):
    ensure_par_dir_exists(meas_path)
    with open(meas_path, 'w+') as meas_file:
        meas_file.write('[\n')
    try:
        async with aiofiles.open(meas_path, 'a') as meas_file:
            while not end_event.is_set():
                line = await line_queue.get()
                if line.startswith(f'@{tname}:dutmeas:'):
                    dutmeas = re.match('@' + tname + r':dutmeas:([^:]+):([^\r\n]+)', line)
                    if dutmeas is None or len(dutmeas.groups()) != 2:
                        print(f'ERROR: malformed DUT measurement line (ignored): {line}')
                        line_queue.task_done()
                        continue
                    dutmeas = dutmeas.groups()
                    await write_out_meas({dutmeas[0] : literal_or_str(dutmeas[1])}, meas_file)
                elif line.startswith(f'@{tname}:psuctl:'):
                    valid, psumeas, psu_configs_loc = await parse_psuline('ctl', line,
                        line_queue, psu_instrs, psu_configs, tname)
                    if not valid:
                        continue
                    # Control and return
                    print(f'PSUCFG: {psumeas}')
                    for name, instr in psu_instrs.items():
                        if  name in psu_configs_loc:
                            psu_configs[name].channels
                            aginstr.set_psu_channel_configs(instr, psu_configs[name].channels, False)
                elif line.startswith(f'@{tname}:psumeas:'):
                    valid, psumeas, psu_configs_loc = await parse_psuline('meas', line,
                        line_queue, psu_instrs, psu_configs, tname)
                    if not valid:
                        continue
                    # Measure and return
                    await async_meas(psu_instrs, psu_configs_loc, meas_file, psumeas[0])
                else:
                    print(f'ERROR: malformed control line (ignored): {line}')
                line_queue.task_done()
    # The task is ending or was cancelled. Pop remaining events and warn for each
    finally:
        with open(meas_path, 'a') as meas_file:
                meas_file.write(']\n')
        while not line_queue.empty():
            line = await line_queue.get()
            print(f'ERROR: terminated before processing control line (ignored): {line}')
            line_queue.task_done()


# TODO: does this need handling of the open serial connection on cancel?
async def uart_handle_serial(line_queue: asyncio.Queue(), uart_dev: str,
    meas_path: str, out_path: str, baudrate: int, tname: str):
    reader, _ = await serial_asyncio.open_serial_connection(url=uart_dev, baudrate=baudrate)
    ensure_par_dir_exists(out_path)
    async with aiofiles.open(out_path, 'w+') as out_file:
        while True:
            line = str(await reader.readline(),  encoding='utf-8')
            # Handle and write any existing IO lines
            if line.startswith(f'@{tname}'):
                line_stripped = line.rstrip()
                line_queue.put_nowait(line_stripped)
            await out_file.write(line)


async def handle_uart(end_event: asyncio.Event, uart_dev: str, meas_path: str, out_path: str,
        psu_instrs: dict, psu_configs: dict, baudrate: int, poll_period: float, tname: str) -> int:
    line_queue = asyncio.Queue()
    # Spawn tasks
    uart_task = asyncio.get_running_loop().create_task(uart_handle_serial(
        line_queue, uart_dev, meas_path, out_path, baudrate, tname))
    control_task = asyncio.get_running_loop().create_task(uart_handle_control_lines(
        end_event, meas_path, line_queue, psu_instrs, psu_configs, tname))
    # Await end event
    while not end_event.is_set():
        await asyncio.sleep(poll_period)
    # Cancel tasks
    uart_task.cancel()
    if not control_task.done():
        print(f'INFO: termination awaiting pending measurements; consider prolonging computation')
        await line_queue.join()
    # There is no failure non-exception failure condition here
    return 0


# ==========
#    GDB
# ==========

async def handle_gdb(end_event: asyncio.Event, 
    binary: str, script_path: str, out_path: str, poll_period: float) -> int:
    return await async_subproc(end_event, [binary, '-x', script_path], 
        out_path, poll_period, sig=signal.SIGKILL)


# =============
#    OpenOCD
# =============

async def handle_ocd(end_event: asyncio.Event, 
    binary: str, script_path: str, out_path: str, poll_period: float) -> int:
    return await async_subproc(end_event, [binary, '-f', script_path],
        out_path, poll_period, mask_return=-15)
