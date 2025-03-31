# Copyright 2025 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Paul Scheffler <paulsc@iis.ee.ethz.ch>
# Thomas Benz <tbenz@iis.ee.ethz.ch>

# Testing setup for Basilisk

SHELL := bash

.SECONDEXPANSION:

# Extracting word nr. $(1) from $(2)-separated list $(3)
pw = $(word $(1), $(subst $(2), ,$(3)))

ROOT   := $(shell realpath .)

################
# Dependencies #
################

DEPS_ROOT   := $(ROOT)/deps
BENDER_ROOT := $(DEPS_ROOT)/.bender
BENDER      := bender -d $(DEPS_ROOT)
CHS_ROOT  	:= $(shell $(BENDER) path cheshire)

# Make sure Cheshire is more up-to-date than any targets run
ifeq ($(shell test -f $(BENDER_ROOT)/.chs_deps && echo 1),)
-include $(BENDER_ROOT)/.chs_deps
endif

# Include Cheshire targets
include $(CHS_ROOT)/cheshire.mk

CHS_SW_FLAGS += -Ofast

############
# Build SW #
############

all: helloworld/helloworld.spm.elf
all: mmopt/mmopt.spm.elf

##############
# Shmoo Plot #
##############

meas-%: $(ROOT)/shmoo/instr.yml.in $(ROOT)/shmoo/run_dutctl.sh
	@echo "=== EXPERIMENT: $(call pw,1,^,$*), VOLTAGE: $(call pw,2,^,$*) mV, FREQ: $(call pw,3,^,$*) MHz ==="
	mkdir -p $(ROOT)/shmoo/runs/$(call pw,1,^,$*)/$(call pw,2,^,$*)^$(call pw,3,^,$*)
	sed -e 's/__V__/$(call pw,2,^,$*)/' -e 's/__F__/$(call pw,3,^,$*)/' $< > $(ROOT)/shmoo/runs/$(call pw,1,^,$*)/$(call pw,2,^,$*)^$(call pw,3,^,$*)/instr.yml
	shmoo/run_dutctl.sh $(call pw,2,^,$*)^$(call pw,3,^,$*) $(call pw,1,^,$*)
	@echo "======"
	@echo

shmoo-run:
	for v in {840..1640..20}; do \
		for f in {4..104..2}; do \
		    make meas-$$v^$$f; \
		done; \
	done

$(ROOT)/shmoo/runs.json:
	$(ROOT)/../../util/parse_runs.py shmoo/runs shmoo/golden.json > $@

$(ROOT)/shmoo/basic.pdf:
	$(ROOT)/../../util/plot_shmoo.py $@ $(ROOT)/shmoo/runs.json

$(ROOT)/shmoo/power.pdf:
	$(ROOT)/../../util/plot_shmoo.py $@ $(ROOT)/shmoo/runs.json core E36231A_1 0

$(ROOT)/shmoo/energy.pdf:
	$(ROOT)/../../util/plot_shmoo.py $@ $(ROOT)/shmoo/runs.json core E36231A_1 0 cycles 25

$(ROOT)/shmoo/eneff.pdf:
	$(ROOT)/../../util/plot_shmoo.py $@ $(ROOT)/shmoo/runs.json core E36231A_1 0 cycles 25 221184

shmoo-plots: $(addprefix $(ROOT)/shmoo/,basic.pdf power.pdf energy.pdf eneff.pdf)
