# DUTCTL: A Flexible Open-Source Framework for Rapid Bring-Up, Characterization, and Remote Operation of Custom-Silicon RISC-V SoCs

**DUTCTL** is part of the [PULP (Parallel Ultra-Low-Power) platform](https://pulp-platform.org/).

It is an opensource framework automating the rapid, ATE-less bring-up and characterization of RISC-V-based SoCs by controlling and coordinating the necessary external devices.
DUTCTL provides the following features:

- It configures and controls any number of network-attached supplies, clock sources, and reset generators described in a customizable configuration.
- It coordinates a full reset-and-power cycle, ensuring statelessness and reproducibility, and provides a fully scriptable GDB debugging session.
- It monitors and stores the SoC’s serial output; through control sequences, the SoC can communicate internal measurements (e.g. computed results, cycle counts) or trigger external measurements (e.g. supply power) with precise timing.
- Through iterated sessions with different parameters and debugging payloads, it enables the design of full test flows and characterization sweeps.
- It enables easy shared and remote access to limited engineering samples for time-efficient testing and software exploration.


## License

DUTCTL is released under Version 2.0 (Apache-2.0) see [`LICENSE`](LICENSE).


## Requirements

This setup is made for Ubuntu 22.04 LTS, the following are required:

* [`riscv-openocd >=0.12.x`](https://github.com/riscv-collab/riscv-openocd)
* [`riscv-gnu-toolchain`](https://github.com/riscv-collab/riscv-gnu-toolchain/releases)
* Python packages in [requirements.txt](requirements.txt)

`Netplan` and `DHCPD` sample configurations can be found in [host/config/system](host/config/system).


## Publication

If you use DUTCTL in your work or research, you can cite us:

```
@inproceedings{benz2024dutctl,
  title     = {DUTCTL: A Flexible Open-Source Framework for Rapid Bring-Up,
               Characterization, and Remote Operation of Custom-Silicon RISC-V SoCs},
  author    = {Thomas Benz and Paul Scheffler and Jennifer Holborn and Luca Benini},
  booktitle = {RISC-V Summit Europe 2024},
  year      = {2024}
}
```
