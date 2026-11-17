# Build/link an OFFLINE payload only. Never patches or flashes an application.
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
CROSS ?= arm-none-eabi-
OUT ?= out
STOCK ?= ../../local/downloads/APP_2C53T_V1.0.7_241205.bin
C_SOURCES := ../payload/parsed.c ../payload/parsed_binding.c ../transport/transport.c ../adapter/stock_adapter.c ../adapter/lifecycle.c
ASM_SOURCES := ../payload/parsed_hooks.S ../payload/key_hook.S ../adapter/lifecycle_hooks.S stock_symbols.S
CFLAGS := -Os -Wall -Wextra -Werror -mcpu=cortex-m4 -mthumb -mfloat-abi=soft -ffreestanding -fno-builtin -fno-common -fno-unwind-tables -fno-asynchronous-unwind-tables -fstack-usage -Wa,--noexecstack
.PHONY: all check-input plan helper
all: check-input
	mkdir -p "$$(dirname '$(OUT)')"
	mkdir '$(OUT)'
	sha256sum $(C_SOURCES) $(ASM_SOURCES) ../payload/*.h ../transport/*.h ../adapter/*.h ../include/*.h payload.ld Makefile input-contract.json plan.py > '$(OUT)/sources.sha256'
	@for src in $(C_SOURCES); do $(CROSS)gcc $(CFLAGS) -c "$$src" -o '$(OUT)'/"$$(basename "$$src" .c).o"; done
	@for src in $(ASM_SOURCES); do $(CROSS)gcc $(CFLAGS) -c "$$src" -o '$(OUT)'/"$$(basename "$$src" .S).o"; done
	$(CROSS)gcc -mcpu=cortex-m4 -mthumb -mfloat-abi=soft -nostdlib -Wl,--fatal-warnings -Wl,--orphan-handling=error -Wl,--build-id=none -Wl,-T,payload.ld -Wl,-Map,'$(OUT)/payload.map' $(foreach s,$(C_SOURCES),$(OUT)/$(notdir $(s:.c=.o))) $(foreach s,$(ASM_SOURCES),$(OUT)/$(notdir $(s:.S=.o))) -o '$(OUT)/payload.elf'
	$(CROSS)objcopy -O binary -j .text -j .ARM.extab -j .ARM.exidx '$(OUT)/payload.elf' '$(OUT)/payload.bin'
	$(CROSS)readelf -W -S -s '$(OUT)/payload.elf' > '$(OUT)/payload-layout.txt'
	$(CROSS)objdump -d '$(OUT)/payload.elf' > '$(OUT)/payload-disassembly.txt'
	sha256sum --check --status '$(OUT)/sources.sha256'
	(cd '$(OUT)' && sha256sum payload.elf payload.bin) > '$(OUT)/artifacts.sha256'
	$(CROSS)size '$(OUT)/payload.elf'
	sha256sum '$(OUT)/payload.bin'
	@echo 'OFFLINE PAYLOAD ONLY: full-image and hardware validation remain required.'
check-input:
	@printf '%s  %s\n' '83271baa03bcbf15200cfb80fa92a8cd0d7c37889b088d382098dcd2c9e0d2b3' '$(STOCK)' | sha256sum --check --status
	@test "$$(stat -c %s '$(STOCK)')" = 486720
	@echo 'Pinned V1.0.7 input verified; original will not be modified.'

PLAN_HELPER ?= dist/fnirsi-plan
PLAN_OUTPUT ?= $(OUT)/experimental-plan.json
plan:
	'$(PLAN_HELPER)' --build . --artifacts '$(OUT)' --stock '$(STOCK)' --output '$(PLAN_OUTPUT)' --tool-prefix '$(CROSS)'
PYINSTALLER ?= pyinstaller
HELPER_WORK ?= /tmp/fnirsi-plan-pyinstaller
helper:
	$(PYINSTALLER) --onefile --name fnirsi-plan --distpath dist --workpath '$(HELPER_WORK)' --specpath '$(HELPER_WORK)' plan.py
