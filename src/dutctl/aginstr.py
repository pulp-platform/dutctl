# Copyright 2025 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Jennifer Holborn <jholborn@student.ethz.ch>
# Paul Scheffler <paulsc@iis.ee.ethz.ch>

# Functions to control and read out Agilent instruments.

import time
import sys
import hashlib
from dataclasses import dataclass, field
import yaml
import pyvisa as vs

Instr = vs.resources.tcpip.TCPIPInstrument


# Hash to bypass config checking. USE AT YOUR OWN RISK.
CFG_BYPASS_HASH = 0xd0a515a1
HASH_MISMATCH_CODE = 17


@dataclass
class PsuChannel:
    vol: float
    cur: float
    volmin: float = 0  # When setting lower voltage, tool will assert-block
    volmax: float = None  # When setting higher voltage, tool will assert-block
    active: bool = True
    fourwire: bool = False
    measure: bool = False  # Whether "global" measure measures this channel
    measure_vol: bool = False  # Whether to measure voltage

    def __post_init__(self):
        # A safe maximum voltage is usually 10% higher than spec.
        if self.volmax is None:
            self.volmax = 1.1*self.vol


@dataclass
class PsuConfig:
    ip: str
    channels: dict = field(default_factory=dict)
    reset_gpio: int = 0    # 0 (default): No reset GPIO
    opmode: str = 'OFF'


@dataclass
class SiggenSource:
    freq: float
    vhi: float
    vlo: float = 0.0
    shape: str = 'SQU'
    leakoff: bool = True
    duty: float = 50.0
    active: bool = True


@dataclass
class SiggenConfig:
    ip: str
    sources: dict = field(default_factory=dict)


def connect_instr(rm: vs.ResourceManager, ip: str) -> Instr:
    ret = rm.open_resource(f'TCPIP0::{ip}::inst0::INSTR')
    return ret


def reset_instr(instr: Instr):
    instr.write('*RST')


# =========================
#    PSU Channel Methods
# =========================

def set_pch_vol_cur(
        instr: Instr, vol: float, cur: float,
        volmin: float, volmax: float, channel: int = 0):
    assert volmin <= vol <= volmax
    if channel == 0:
        instr.write(f'APPLY {vol}, {cur}')
    else:
        instr.write(f'APPLY CH{channel}, {vol}, {cur}')
    time.sleep(0.05)    # wait until voltage is really set


def set_pch_fourwire(instr, fourwire: bool = True, channel: int = 0):
    channel = 1 if channel == 0 else channel
    instr.write(f'VOLTAGE:SENSE:SOURCE {"EXTERNAL" if fourwire else "INTERNAL"}, (@{channel})')


def set_pch_active(instr: Instr, active: bool = True, channel: int = 0):
    channel = 1 if channel == 0 else channel
    instr.write(f'OUTPUT:state {"ON" if active else "OFF"},(@{channel})')


def meas_pch_vol_or_cur(instr: Instr, tpe: str = 'VOLT', channel: int = 0) -> float:
    assert tpe.startswith('VOLT') or tpe.startswith('CURR')
    channel = 1 if channel == 0 else channel
    return float(instr.query(f'MEASURE:SCALAR:{tpe}:DC? (@{channel})'))


# =================
#    PSU Methods
# =================

def set_psu_opmode(instr: Instr, opmode: str = 'OFF'):
    assert opmode in ('OFF', 'PAR', 'SER')
    instr.write(f'OUTPUT:PAIR {opmode}')


def set_psu_gpio_state(instr: Instr, pin: int = 1, val: bool = True):
    assert pin > 0
    instr.write(f'DIGITAL:PIN{pin}:FUNCTION DIO')
    instr.write(f'DIGITAL:PIN{pin}:POLARITY POSITIVE')
    instr.write(f'DIGITAL:OUTPUT:DATA {int(val)}')


def set_psu_channel_configs(instr: Instr, channel_configs: dict, toggle_output_state: bool = True):
    for chan, cfg in channel_configs.items():
        set_pch_vol_cur(instr, cfg.vol, cfg.cur, cfg.volmin, cfg.volmax, chan)
        set_pch_fourwire(instr, cfg.fourwire, chan)
        if toggle_output_state:
            set_pch_active(instr, cfg.active, chan)


# ===========================
#    Siggen Source Methods
# ===========================

def set_sigsrc_freq(instr: Instr, freq: float, source: int = 1):
    assert source > 0
    instr.write(f'SOURCE{source}:FREQ {freq}')


def set_sigsrc_levels(instr: Instr, vhi: float, vlo: float, source: int = 1):
    assert source > 0
    instr.write(f'SOURCE{source}:VOLT:HIGH {vhi}')
    instr.write(f'SOURCE{source}:VOLT:LOW {vlo}')


def set_sigsrc_shape(instr: Instr, shape: str, duty: float, source: int = 1):
    assert shape in ('SQU', 'SIN', 'TRI', 'RAMP', 'NRAN')
    assert 0 < duty < 100
    instr.write(f'SOURCE{source}:FUNC {shape}')
    instr.write(f'SOURCE{source}:FUNC:{shape}:DCYC {duty}')


def set_sigsrc_active(instr: Instr, active: bool, source: int = 1):
    assert source > 0
    instr.write(f'OUTPUT{source} {"ON" if active else "OFF"}')


# ====================
#    Siggen Methods
# ====================

def set_siggen_source_configs(instr: Instr, source_configs: dict, toggle_output_state: bool = True):
    for src, cfg in source_configs.items():
        set_sigsrc_freq(instr, cfg.freq, src)
        set_sigsrc_levels(instr, cfg.vhi, cfg.vlo, src)
        set_sigsrc_shape(instr, cfg.shape, cfg.duty, src)
        if toggle_output_state:
            set_sigsrc_active(instr, cfg.active, src)


# ==========================
#    System-level Methods
# ==========================

# Return instrument config from YML file
def config_from_yml(yaml_file: str) -> (dict, bool):
    # Load file
    with open(yaml_file, 'r', encoding='utf-8') as file:
        cfg = yaml.safe_load(file)
    # Check hash
    given_hash = int(cfg['safety_hash'])
    del cfg['safety_hash']
    actual_hash = int(hashlib.md5(str(cfg).encode('utf-8')).hexdigest()[:16], 16)
    if given_hash == CFG_BYPASS_HASH:
        print('WARNING: Bypassing instrument config hash check; '
              f'actual is 0x{actual_hash:x}.', file=sys.stderr)
    elif given_hash != actual_hash:
        print('ERROR: Instrument config hash check failed; '
              f' given 0x{given_hash:x} vs. actual 0x{actual_hash:x}!', file=sys.stderr)
        sys.exit(HASH_MISMATCH_CODE)
    # Parse supplies into objects
    if 'supplies' in cfg:
        for pname in list(cfg['supplies'].keys()):
            ccfgs = {}
            for cidx, ccfg in cfg['supplies'][pname]['channels'].items():
                ccfgs[cidx] = PsuChannel(**ccfg)
            cfg['supplies'][pname]['channels'] = ccfgs
            cfg['supplies'][pname] = PsuConfig(**cfg['supplies'][pname])
    # Parse siggens into objects
    if 'siggens' in cfg:
        for gname in list(cfg['siggens'].keys()):
            gcfgs = {}
            for sidx, scfg in cfg['siggens'][gname]['sources'].items():
                gcfgs[sidx] = SiggenSource(**scfg)
            cfg['siggens'][gname]['sources'] = gcfgs
            cfg['siggens'][gname] = SiggenConfig(**cfg['siggens'][gname])
    return cfg


# Connect to collection of instruments by their IP
def connect_instrs(rm: vs.ResourceManager, configs: dict) -> dict:
    return {name: connect_instr(rm, cfg.ip) for name, cfg in configs.items()}


# Issue reset on all PSUs
def reset(instrs: dict, psu_configs: dict, initial_low: bool = False, t_rst: float = 0.1):
    for name, cfg in psu_configs.items():
        if not initial_low and cfg.reset_gpio:
            set_psu_gpio_state(instrs[name], cfg.reset_gpio, True)
    for name, cfg in psu_configs.items():
        if cfg.reset_gpio:
            set_psu_gpio_state(instrs[name], cfg.reset_gpio, False)
    time.sleep(t_rst)
    for name, cfg in psu_configs.items():
        if cfg.reset_gpio:
            set_psu_gpio_state(instrs[name], cfg.reset_gpio, True)


# Power off all PSUs
def power_off(instrs: dict, psu_configs: dict, ganged: bool = True):
    # If supplies are ganged, switch off only one
    if ganged:
        set_pch_active(next(iter(instrs.values())), False)
    else:
        for name in psu_configs.keys():
            set_pch_active(instrs[name], False)


# Power-cycle all supplies, reapplying config, and assert reset(s)
def power_reset_cycle(
        instrs: dict, psu_configs: dict, ganged: bool = True,
        t_rst: float = 0.1, rst_instr: bool = True):
    # Shut down all channels of all supplies.
    power_off(instrs, psu_configs, ganged)
    # Apply configs; this will reset, then turn on active channels.
    # Also raise reset where it happened to be low.
    for name, cfg in psu_configs.items():
        if rst_instr:
            reset_instr(instrs[name])
        if None not in cfg.channels:
            set_psu_opmode(instrs[name], cfg.opmode)
        set_psu_channel_configs(instrs[name], cfg.channels, not ganged)
    # If supplies are ganged: turn one on
    if ganged:
        set_pch_active(next(iter(instrs.values())), True)
    # Toggle GPIO in channels with reset
    reset(instrs, psu_configs, True, t_rst)


# Measure out all supplies specified
def meas_vol_cur(instrs: dict, psu_configs: dict, measure_all: bool = False) -> dict:
    ret = {}
    # Measure
    for pname, pcfg in psu_configs.items():
        for cidx, ccfg in pcfg.channels.items():
            if not ccfg.measure and not measure_all:
                continue
            if pname not in ret:
                ret[pname] = {}
            if cidx not in ret[pname]:
                ret[pname][cidx] = {}
            ret[pname][cidx]['cur'] = meas_pch_vol_or_cur(instrs[pname], 'CURR', cidx)
            if ccfg.measure_vol:
                ret[pname][cidx]['vol'] = meas_pch_vol_or_cur(instrs[pname], 'VOLT', cidx)
    return ret


# Turn off signal generators
def siggens_off(instrs: dict, siggen_configs: dict):
    for gname, gcfg in siggen_configs.items():
        for sidx in gcfg.sources:
            set_sigsrc_active(instrs[gname], False, sidx)


# Turn off only those siggens supposed for leaking
def siggens_leak_off(instrs: dict, siggen_configs: dict):
    for gname, gcfg in siggen_configs.items():
        for sidx in gcfg.sources:
            if gcfg.sources[sidx].leakoff:
                print(gcfg.sources[sidx])
                set_sigsrc_active(instrs[gname], False, sidx)


# Reconfigure signal generators
def reconf_siggens(
        instrs: dict, siggen_configs: dict,
        stop_instr: bool = True, rst_instr: bool = False):
    if stop_instr:
        siggens_off(instrs, siggen_configs)
    # Reset generators if requested, then set up sources
    for gname, gcfg in siggen_configs.items():
        if rst_instr:
            reset_instr(instrs[gname])
        set_siggen_source_configs(instrs[gname], gcfg.sources)
