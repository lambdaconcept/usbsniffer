#!/usr/bin/env python3
from litex.build.openocd import OpenOCD

prog = OpenOCD("openocd/openocd.cfg",
        flash_proxy_basename="bscan_spi_xc7a50t.bit")
prog.set_flash_proxy_dir("openocd")
prog.flash(0x0, "build/gateware/top.bin")
