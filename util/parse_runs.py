#! /usr/bin/env python3
#
# Copyright 2025 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Paul Scheffler <paulsc@iis.ee.ethz.ch>

# Parses and checks a set of DUTCTL run measurements at parameters. Expects
# a directory of log directories with names that are multiple caret-separated
# string parameters. For example, a Schmoo measurement set (v vs f) could have
# directories named `<v_in_mV>^<f_in_Mhz>`, e.g. `1200^50`.
#
# The parameters will be parsed into a nested dict with str keys corresponding
# to the parameters, with the leftmost parameter being the highest level. The
# JSON measurements will be flattened, assuming every measurement is a single-
# key dict with a unique key, and become the values to these parameter keys.
#
# Another JSON file can be provided with keys and golden values which should be
# checked; this, together with whether a JSON report is parseable and has the
# correct keys, determines the value of an additional boolean field `correct`
# for each key.

import os
import sys
import glob
import json
from collections import defaultdict


# DUTCTL avoids name clashes by using a list of dicts.
# In our case, we know these have single keys and unique names,
# so we can parse them into a simpler dict.
def dutctl_list_to_dict(lst: list):
    ret = {}
    for item in lst:
        for key, val in item.items():
            ret[key] = val
    return ret


def main(runs_dir: str, gold_path: str = None) -> int:
    # If provided, open golden result file first
    gold = {}
    if gold_path is not None:
        with open(gold_path, 'r', encoding='utf-8') as file:
            gold = json.load(file)

    # Defaultdicts self-populate on keying, which simplifies things
    dd_tree = lambda : defaultdict(dd_tree)  # pylint: disable=unnecessary-lambda-assignment
    runs = dd_tree()

    # Iterate over available runs, check correctness, and add to dict
    for path in glob.glob(f'{runs_dir}/**/measure0.json'):

        # Check basic correctness: file is JSON and has all needed keys.
        with open(path, 'r', encoding='utf-8') as file:
            try:
                run_data = dutctl_list_to_dict(json.load(file))
                if gold_path is not None:
                    run_data['correct'] = all(k in run_data for k in gold)
            except json.decoder.JSONDecodeError:
                if gold_path is not None:
                    run_data = {'correct': False}
                continue
        # Check logical correctness: measurements should match golden ones.
        if gold_path is not None and run_data['correct']:
            run_data['correct'] = all(run_data[k] == gold[k] for k in gold)
        # Write data to run dict using recursive indexing
        curr_dict = runs
        run_name = os.path.basename(os.path.dirname(path))
        levels = run_name.split('^')
        for g in levels[:-1]:
            curr_dict = curr_dict[g]
        curr_dict[levels[-1]] = run_data

    # Write out results as JSON (pipe to file if needed)
    print(json.dumps(runs, indent=2))

    return 0


if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    sys.exit(main(*sys.argv[1:]))
