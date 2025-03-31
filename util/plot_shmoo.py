#! /usr/bin/env python3
#
# Copyright 2025 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Thomas Benz <tbenz@iis.ee.ethz.ch>
# Paul Scheffler <paulsc@iis.ee.ethz.ch>

# Create a Shmoo plot from a parsed set of runs. The runs are expected to have
# the parameters `<v_in_mV>^<f_in_Mhz>`, e.g. `1200^50`. Furthermore, both the
# frequency and voltage steps must be constant and each voltage step must have
# as many or fewer lower-contiguous frequency measurements as the lowest one.
#
# For incorrect runs, the fields are white. For correct runs, the field color
# is green by default. If a third argument is added, the color represents the
# power indicated by a supply measurement of that name. A fourth and fifth
# argument then select the core supply and channel. If a sixth and optionally
# seventh argument (see below) are passed, energy is plotted. An eigth argument
# (see below) instead plots energy efficiency.
#
# If sixth argument is passed, it is considered the name of a cycle
# measurement (int or float), and combined with the frequency and power to
# color each correct run by its energy. A seventh argument specifies the number
# of workload runs counted in the cycle count. It defaults to 1, i.e. assumes
# by default that the fifth arg counts the cycles of one iteration. Finally,
# an eight argument specifies the number of operations performed in the
# provided cycle count.

import sys
import json
from collections import defaultdict
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

# We don't need an interactive backend for matplotlib
mpl.use('Agg')


# pylint: disable=too-many-locals
def generate_data(
        runs_path: str,
        pmeas: str = None, psupply: str = None, pchan: str = None,
        cmeas: str = None, citer: str = '1', ops : str = None) -> dict:
    # Read runs file
    with open(runs_path, 'r', encoding='utf-8') as file:
        runs = json.load(file)

    # Extract 1D axes: cast & sort voltages, then extract freq steps from lowest one
    vs_mv = sorted([int(vstr) for vstr in runs.keys()])
    fs_mhz = sorted([int(fstr) for fstr in runs[str(vs_mv[0])].keys()])

    # Extract 2D data from runs
    ret = defaultdict(list)
    for v_mv in vs_mv:
        row_corrects = []
        row_ps_mw = []
        row_es_mj = []
        row_effs_mflop_per_s_per_w = []
        for f_mhz in fs_mhz:
            # Defaults: incorrect, NaNs (unplotted) for numbers
            correct = np.nan
            p_mw = np.nan
            e_mj = np.nan
            eff_mflop_per_s_per_w = np.nan
            if str(f_mhz) in runs[str(v_mv)]:
                run = runs[str(v_mv)][str(f_mhz)]
                if run['correct']:
                    correct = 1
                    if pmeas is not None:
                        current_a = float(run[pmeas][psupply][pchan]['cur'])
                        p_mw = float(v_mv) * current_a
                    if cmeas is not None:
                        tmeas_s = float(run[cmeas]) / float(citer) * 1e-6 / float(f_mhz)
                        e_mj = p_mw * tmeas_s
                    if ops is not None:
                        eff_mflop_per_s_per_w = float(ops) * 1e-3 / e_mj
            row_corrects.append(correct)
            row_ps_mw.append(p_mw)
            row_es_mj.append(e_mj)
            row_effs_mflop_per_s_per_w.append(eff_mflop_per_s_per_w)
        ret['corrects'].append(row_corrects)
        ret['ps_mw'].append(row_ps_mw)
        ret['es_mj'].append(row_es_mj)
        ret['effs_mflop_per_s_per_w'].append(row_effs_mflop_per_s_per_w)

    # Add voltage (in volts) and frequency and return data
    ret['vs_v'] = 1e-3 * np.array(vs_mv)
    ret['fs_mhz'] = fs_mhz
    return dict(ret)


def main(out_file: str, *genargs) -> int:
    # Generate data to be plotted
    data = generate_data(*genargs)

    # Determine plotting mode from args, assign correct data
    bar_cmap = mpl.colormaps['viridis']
    bar_cmap.set_under('white')
    bar_show = True
    if genargs[6] is not None:
        bar_legend = 'En. Eff. (MFLOP/s/W)'
        bar_data = data['effs_mflop_per_s_per_w']
    elif genargs[4] is not None:
        bar_legend = 'Energy (mJ)'
        bar_data = data['es_mj']
    elif genargs[1] is not None:
        bar_legend = 'Power (mW)'
        bar_data = data['ps_mw']
    else:
        bar_cmap = mpl.colors.ListedColormap(['green'])
        bar_show = False
        bar_legend = None
        bar_data = data['corrects']

    # Initialize the figure and plot
    scale = 1.15
    fig = plt.figure(figsize=(3.3*scale, 2.0*scale))
    ax = plt.subplot(111)

    # Style axes
    xdata = data['vs_v']
    ydata = data['fs_mhz']
    xticks = xdata[::5]
    yticks = ydata[::6]
    ax.set_xlabel('Frequency (MHz)', fontsize=10)
    ax.set_ylabel('Core Voltage (V)', fontsize=10)
    plt.xticks(xticks, rotation=0)
    ax.set_yticks(yticks)
    ax.set_xticklabels(xticks)
    ax.set_yticklabels(yticks)
    ax.xaxis.set_major_formatter(lambda val: f'{val:.0f}')
    ax.yaxis.set_major_formatter(lambda val: f'{val:1.2f}')

    # Plot the desired data and save
    c = ax.pcolormesh(ydata, xdata, bar_data, cmap=bar_cmap, edgecolor='silver', linewidth=0.0)
    if bar_show:
        cbar = fig.colorbar(c, ax=ax)
        cbar.set_label(bar_legend, fontsize=10)
    plt.savefig(out_file, bbox_inches='tight', pad_inches=0.01)

    return 0


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    sys.exit(main(*sys.argv[1:]))
