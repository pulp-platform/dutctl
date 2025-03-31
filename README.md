# DUTCTL

DUTCTL is an open-source framework for the rapid *bring-up*, *characterization*, and *remote operation* of custom RISC-V SoCs. It controls and coordinates instruments and adapters connected to a RISC-V device under test (DUT) to enable automated and reproducible silicon evaluation without a traditional ATE setup.

DUTCTL is developed as part of the PULP project, a joint effort between ETH Zurich and the University of Bologna.

## Features

DUTCTL can configure multiple lab instruments, such as power supplies and signal generators, at once using [SCPI](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments) over IP. The IP address and configuration for each instrument are passed in a single YAML file. Each power supply can further have one of its GPIOs configured to serve as a DUT reset.

To enable the execution and evaluation of full workloads, DUTCTL can run scripted OpenOCD and GDB sessions and capture their output in log files. It can also log the DUT's serial output if desired.

The DUT's serial output may contain commands to DUTCTL, which are prefixed with `@dutctl`. These commands can communicate internal measurements, trigger supply measurements, or even reconfigure supplies.

Together, these features enable fully automated and reproducible experiments. By repeatedly invoking DUTCTL from a script, full test suites and measurement sweeps can be run.

## Usage

We provide a simple test environment for the [Basilisk SoC](https://github.com/pulp-platform/cheshire-ihp130-o) as an example DUTCTL setup in `target/basilisk/`. This setup also leverages reusable utility scripts (data parsing and Shmoo plotting) found in `util/`.

For a brief explanation of all command-line arguments, run:

```
./dutctl --help
```

## Requirements

DUTCTL has the following dependencies:

* [RISC-V OpenOCD](https://github.com/riscv-collab/riscv-openocd)  `>=0.12.0`
* [RISC-V GNU toolchain](https://github.com/riscv-collab/riscv-gnu-toolchain/releases)
* Python packages in `requirements.txt`

We strongly recommend creating a local DHCP server and configuring static IPs for all used instruments. Please find example `dhcpd` and `netplan` configurations for this in `util/host_setup/`.

## License

DUTCTL is licensed under Apache 2.0 (see `LICENSE`).

## Publication

If you use DUTCTL in your work, you can cite us:

```
@inproceedings{benz2024dutctl,
  title     = {DUTCTL: A Flexible Open-Source Framework for Rapid Bring-Up,
               Characterization, and Remote Operation of Custom-Silicon RISC-V
               SoCs},
  author    = {Thomas Benz and Paul Scheffler and
               Jennifer Holborn and Luca Benini},
  booktitle = {RISC-V Summit Europe 2024},
  year      = {2024}
}
```
