# Copyright 2025 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Paul Scheffler <paulsc@iis.ee.ethz.ch>
# Thomas Benz <tbenz@iis.ee.ethz.ch>

# Main entry point for dutctl CLI utility

import sys
import signal
import asyncio

from dutctl import dutctl


def term(sig: int = 0, frame=None):     # pylint: disable=unused-argument
    print(f'\nINFO: terminating due to caught signal {sig}')
    dutctl.end_event.set()


if __name__ == '__main__':
    # Register termination handlers
    signal.signal(signal.SIGTERM, term)
    signal.signal(signal.SIGINT, term)
    signal.signal(signal.SIGQUIT, term)
    signal.signal(signal.SIGABRT, term)
    # Launch main
    sys.exit(asyncio.run(dutctl.main(sys.argv[1:])))
