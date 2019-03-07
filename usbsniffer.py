#!/usr/bin/env python3

import math

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform

from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.integration.cpu_interface import get_csr_header
from litex.soc.interconnect import stream
from litex.soc.cores.uart import UARTWishboneBridge, RS232PHY
from litex.soc.cores.gpio import GPIOOut

from litedram import sdram_init
from litedram.modules import MT41K256M16
from litedram.phy import a7ddrphy

from gateware.usb import USBCore
from gateware.etherbone import Etherbone
from gateware.ft601 import FT601Sync, phy_description
from gateware.ulpi import ULPIPHY, ULPICore, ULPIFilter
from gateware.packer import LTCore, LTPacker
from gateware.iti import ITIPacker
from gateware.wrapper import WrapCore
from gateware.dramfifo import LiteDRAMFIFO
from gateware.spi import SPIMaster
from gateware.flash import Flash

from litescope import LiteScopeAnalyzer


_io = [
    ("clk100", 0, Pins("J19"), IOStandard("LVCMOS33")),

    ("rgb_led", 0,
        Subsignal("r", Pins("W2")),
        Subsignal("g", Pins("Y1")),
        Subsignal("b", Pins("W1")),
        IOStandard("LVCMOS33"),
    ),

    ("rgb_led", 1,
        Subsignal("r", Pins("AA1")),
        Subsignal("g", Pins("AB1")),
        Subsignal("b", Pins("Y2")),
        IOStandard("LVCMOS33"),
    ),

    ("serial", 0,
        Subsignal("tx", Pins("U21")), # FPGA_GPIO0
        Subsignal("rx", Pins("T21")), # FPGA_GPIO1
        IOStandard("LVCMOS33"),
    ),

    ("ddram", 0,
        Subsignal("a", Pins(
            "M2 M5 M3 M1 L6 P1 N3 N2",
            "M6 R1 L5 N5 N4 P2 P6"),
            IOStandard("SSTL15")),
        Subsignal("ba", Pins("L3 K6 L4"), IOStandard("SSTL15")),
        Subsignal("ras_n", Pins("J4"), IOStandard("SSTL15")),
        Subsignal("cas_n", Pins("K3"), IOStandard("SSTL15")),
        Subsignal("we_n", Pins("L1"), IOStandard("SSTL15")),
        Subsignal("dm", Pins("G3 F1"), IOStandard("SSTL15")),
        Subsignal("dq", Pins(
            "G2 H4 H5 J1 K1 H3 H2 J5",
            "E3 B2 F3 D2 C2 A1 E2 B1"),
            IOStandard("SSTL15"),
            Misc("IN_TERM=UNTUNED_SPLIT_50")),
        Subsignal("dqs_p", Pins("K2 E1"), IOStandard("DIFF_SSTL15")),
        Subsignal("dqs_n", Pins("J2 D1"), IOStandard("DIFF_SSTL15")),
        Subsignal("clk_p", Pins("P5"), IOStandard("DIFF_SSTL15")),
        Subsignal("clk_n", Pins("P4"), IOStandard("DIFF_SSTL15")),
        Subsignal("cke", Pins("J6"), IOStandard("SSTL15")),
        Subsignal("odt", Pins("K4"), IOStandard("SSTL15")),
        Subsignal("reset_n", Pins("G1"), IOStandard("SSTL15")),
        Misc("SLEW=FAST"),
    ),

    ("flash", 0,
        Subsignal("cs_n", Pins("T19")),
        Subsignal("mosi", Pins("P22")),
        Subsignal("miso", Pins("R22")),
        Subsignal("vpp", Pins("P21")),
        Subsignal("hold", Pins("R21")),
        IOStandard("LVCMOS33")
    ),

    ("usb_fifo_clock", 0, Pins("D17"), IOStandard("LVCMOS33")),
    ("usb_fifo", 0,
        Subsignal("rst", Pins("K22")),
        Subsignal("data", Pins("A16 F14 A15 F13 A14 E14 A13 E13 B13 C15 C13 C14 B16 E17 B15 F16",
                               "A20 E18 B20 F18 D19 D21 E19 E21 A21 B21 A19 A18 F20 F19 B18 B17")),
        Subsignal("be", Pins("K16 L16 G20 H20")),
        Subsignal("rxf_n", Pins("M13")),
        Subsignal("txe_n", Pins("L13")),
        Subsignal("rd_n", Pins("K19")),
        Subsignal("wr_n", Pins("M15")),
        Subsignal("oe_n", Pins("L21")),
        Subsignal("siwua", Pins("M16")),
        IOStandard("LVCMOS33"), Misc("SLEW=FAST")
    ),

    ("ulpi_sw", 0,
        Subsignal("s", Pins("Y8")),
        Subsignal("oe_n", Pins("Y9")),
        IOStandard("LVCMOS33"),
    ),

    ("ulpi_clock", 0, Pins("W19"), IOStandard("LVCMOS33")),
    ("ulpi", 0,
        Subsignal("data", Pins("AB18 AA18 AA19 AB20 AA20 AB21 AA21 AB22")),
        Subsignal("dir", Pins("W21")),
        Subsignal("stp", Pins("Y22")),
        Subsignal("nxt", Pins("W22")),
        Subsignal("rst", Pins("V20")),
        IOStandard("LVCMOS33"), Misc("SLEW=FAST")
    ),

    ("ulpi_clock", 1, Pins("V4"), IOStandard("LVCMOS33")),
    ("ulpi", 1,
        Subsignal("data", Pins("AB2 AA3 AB3 Y4 AA4 AB5 AA5 AB6")),
        Subsignal("dir", Pins("AB7")),
        Subsignal("stp", Pins("AA6")),
        Subsignal("nxt", Pins("AB8")),
        Subsignal("rst", Pins("AA8")),
        IOStandard("LVCMOS33"), Misc("SLEW=FAST")
    ),
]


class Platform(XilinxPlatform):
    default_clk_name = "clk100"
    default_clk_period = 10.0

    def __init__(self, toolchain="vivado", programmer="vivado"):
        XilinxPlatform.__init__(self, "xc7a35t-fgg484-1", _io,
                                toolchain=toolchain)
        self.toolchain.bitstream_commands = \
            ["set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]",
             "set_property BITSTREAM.CONFIG.CONFIGRATE 40 [current_design]"]
        self.toolchain.additional_commands = \
            ["write_cfgmem -force -format bin -interface spix4 -size 16 "
             "-loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"]
        self.programmer = programmer
        self.add_platform_command("set_property INTERNAL_VREF 0.750 [get_iobanks 35]")


class _CRG(Module, AutoCSR):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain("sys")
        self.clock_domains.cd_ulpi0 = ClockDomain("ulpi0")
        self.clock_domains.cd_ulpi1 = ClockDomain("ulpi1")
        self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)
        self.clock_domains.cd_clk200 = ClockDomain()

        self.clock_domains.cd_usb = ClockDomain()

        # usb clock domain (100MHz from usb)
        self.comb += self.cd_usb.clk.eq(platform.request("usb_fifo_clock"))
        self.comb += self.cd_usb.rst.eq(self.cd_sys.rst)

        # ulpi0 clock domain (60MHz from ulpi0)
        self.comb += self.cd_ulpi0.clk.eq(platform.request("ulpi_clock", 0))

        # ulpi1 clock domain (60MHz from ulpi1)
        self.comb += self.cd_ulpi1.clk.eq(platform.request("ulpi_clock", 1))

        clk100 = platform.request("clk100")

        # sys & ddr clock domains
        pll_locked = Signal()
        pll_fb = Signal()
        pll_sys = Signal()
        pll_sys4x = Signal()
        pll_sys4x_dqs = Signal()
        pll_clk200 = Signal()
        self.specials += [
            Instance("PLLE2_BASE",
                     p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                     # VCO @ 1600 MHz
                     p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=10.0,
                     p_CLKFBOUT_MULT=16, p_DIVCLK_DIVIDE=1,
                     i_CLKIN1=clk100, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

                     # 100 MHz
                     p_CLKOUT0_DIVIDE=16, p_CLKOUT0_PHASE=0.0,
                     o_CLKOUT0=pll_sys,

                     # 400 MHz
                     p_CLKOUT1_DIVIDE=4, p_CLKOUT1_PHASE=0.0,
                     o_CLKOUT1=pll_sys4x,

                     # 400 MHz dqs
                     p_CLKOUT2_DIVIDE=4, p_CLKOUT2_PHASE=90.0,
                     o_CLKOUT2=pll_sys4x_dqs,

                     # 200 MHz
                     p_CLKOUT3_DIVIDE=8, p_CLKOUT3_PHASE=0.0,
                     o_CLKOUT3=pll_clk200,
            ),
            Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
            Instance("BUFG", i_I=pll_sys4x, o_O=self.cd_sys4x.clk),
            Instance("BUFG", i_I=pll_sys4x_dqs, o_O=self.cd_sys4x_dqs.clk),
            Instance("BUFG", i_I=pll_clk200, o_O=self.cd_clk200.clk),
            AsyncResetSynchronizer(self.cd_sys, ~pll_locked),
            AsyncResetSynchronizer(self.cd_clk200, ~pll_locked)
        ]

        reset_counter = Signal(4, reset=15)
        ic_reset = Signal(reset=1)
        self.sync.clk200 += \
            If(reset_counter != 0,
                reset_counter.eq(reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        self.specials += Instance("IDELAYCTRL", i_REFCLK=ClockSignal("clk200"), i_RST=ic_reset)


class BlinkerKeep(Module):
    def __init__(self, s, timeout=int(1e6)):
        self.o = Signal()

        # # #

        counter = Signal(max=timeout+1)
        self.sync += [
            If(s,
                counter.eq(timeout),
            ).Elif(counter > 0,
                counter.eq(counter - 1),
            ).Else(
                counter.eq(0),
            )
        ]

        self.comb += self.o.eq(counter > 0)


class BlinkerRGB(Module, AutoCSR):
    def __init__(self, leds, sr, sg, sb, divbits=27):
        self.forceblink = CSRStorage()

        # # #

        self.submodules.keepr = BlinkerKeep(sr)
        self.submodules.keepg = BlinkerKeep(sg)
        self.submodules.keepb = BlinkerKeep(sb)

        counter = Signal(divbits + 2)
        self.sync += counter.eq(counter + 1)

        self.comb += [
            If(self.forceblink.storage,
                leds.r.eq(~counter[divbits-3]),
                leds.g.eq(~counter[divbits-2]),
                leds.b.eq(~counter[divbits-1]),
            ).Else(
                leds.r.eq(~self.keepr.o),
                leds.g.eq(~self.keepg.o),
                leds.b.eq(~self.keepb.o),
            )
        ]


class USBSnifferSoC(SoCSDRAM):
    csr_peripherals = [
        "flash",
        "ddrphy",
        "ulpi_phy0",
        "ulpi_phy1",
        "ulpi_core0",
        "ulpi_core1",
        "ulpi_filter0",
        "ulpi_filter1",
        "ulpi_sw_oe_n",
        "ulpi_sw_s",
        "itipacker0",
        "itipacker1",
        "blinker0",
        "blinker1",
        "analyzer",
    ]
    csr_map_update(SoCSDRAM.csr_map, csr_peripherals)

    usb_map = {
        "wishbone": 0,
        "ulpi0":    1,
        "ulpi1":    2,
    }

    def __init__(self, platform, with_analyzer=False, with_loopback=False):
        clk_freq = int(100e6)
        SoCSDRAM.__init__(self, platform, clk_freq,
            cpu_type=None,
            l2_size=32,
            csr_data_width=32, csr_address_width=15, # required for flash spi
            integrated_rom_size=0,
            integrated_sram_size=0x8000,
            with_uart=False,
            ident="USB2Sniffer design",
            with_timer=False
        )
        self.submodules.crg = _CRG(platform)

        # flash spi
        self.submodules.flash = Flash(platform.request("flash"), div=math.ceil(clk_freq/25e6))

        # sdram
        self.submodules.ddrphy = a7ddrphy.A7DDRPHY(platform.request("ddram"))
        sdram_module = MT41K256M16(self.clk_freq, "1:4")
        self.register_sdram(self.ddrphy,
                            sdram_module.geom_settings,
                            sdram_module.timing_settings)

        # sdram fifo
        depth = 128 * 1024 * 1024
        self.submodules.fifo = LiteDRAMFIFO([("data", 8)], depth, 0, self.sdram.crossbar,
                                            preserve_first_last=False)

        # debug wishbone
        self.add_cpu(UARTWishboneBridge(platform.request("serial"), clk_freq, baudrate=3e6))
        self.add_wb_master(self.cpu.wishbone)

        # usb phy
        usb_pads = platform.request("usb_fifo")
        self.submodules.usb_phy = FT601Sync(usb_pads, dw=32, timeout=1024)

        if with_loopback:
            self.submodules.usb_loopback_fifo = stream.SyncFIFO(phy_description(32), 2048)
            self.comb += [
                self.usb_phy.source.connect(self.usb_loopback_fifo.sink),
                self.usb_loopback_fifo.source.connect(self.usb_phy.sink)
            ]
        else:
            # usb core
            self.submodules.usb_core = USBCore(self.usb_phy, clk_freq)

            # usb <--> wishbone
            self.submodules.etherbone = Etherbone(self.usb_core, self.usb_map["wishbone"])
            self.add_wb_master(self.etherbone.master.bus)

            # ulpi switch
            ulpi_sw = platform.request("ulpi_sw")
            self.submodules.ulpi_sw_oe_n = GPIOOut(ulpi_sw.oe_n)
            self.submodules.ulpi_sw_s = GPIOOut(ulpi_sw.s)

            # ulpi 0
            self.submodules.ulpi_phy0 = ULPIPHY(platform.request("ulpi", 0), cd="ulpi0")
            self.submodules.ulpi_core0 = ULPICore(self.ulpi_phy0)

            # ulpi 1
            self.submodules.ulpi_phy1 = ULPIPHY(platform.request("ulpi", 1), cd="ulpi1")
            self.submodules.ulpi_core1 = ULPICore(self.ulpi_phy1)

            # usb <--> ulpi0
            self.submodules.itipacker0 = ITIPacker()
            self.submodules.wrapcore0 = WrapCore(self.usb_core, self.usb_map["ulpi0"])
            self.comb += [
                self.ulpi_core0.source.connect(self.itipacker0.sink),
                self.itipacker0.source.connect(self.fifo.sink),
                self.fifo.source.connect(self.wrapcore0.sink),
            ]

            # leds
            led0 = platform.request("rgb_led", 0)
            self.submodules.blinker0 = BlinkerRGB(led0,
                    self.etherbone.packet.tx.source.valid,
                    0, self.etherbone.packet.rx.sink.valid)

            led1 = platform.request("rgb_led", 1)
            self.submodules.blinker1 = BlinkerRGB(led1,
                    self.ulpi_core0.source.valid,
                    0, self.wrapcore0.sender.source.valid)

        # timing constraints
        self.crg.cd_sys.clk.attr.add("keep")
        self.crg.cd_usb.clk.attr.add("keep")
        self.platform.add_period_constraint(self.crg.cd_sys.clk, 10.0)
        self.platform.add_period_constraint(self.crg.cd_usb.clk, 10.0)

        if with_analyzer:
            analyzer_signals = [
                self.ulpi_core0.source.valid,
                self.ulpi_core0.source.ready,
                self.ulpi_core0.source.data,
                self.itipacker0.source.valid,
                self.itipacker0.source.ready,
                self.itipacker0.source.data,
                self.fifo.source.valid,
                self.fifo.source.ready,
                self.fifo.source.data,
                self.wrapcore0.sender.source.valid,
                self.wrapcore0.sender.source.ready,
                self.wrapcore0.sender.source.data,
            ]
            self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals, 1024, clock_domain="sys")

    def do_exit(self, vns):
        if hasattr(self, "analyzer"):
            self.analyzer.export_csv(vns, "test/analyzer.csv")

    def generate_software_header(self):
        csr_header = get_csr_header(self.get_csr_regions(),
                                    self.get_constants(),
                                    with_access_functions=True)
        tools.write_to_file(os.path.join("software/generated/csr.h"), csr_header)

        phy_header = sdram_init.get_sdram_phy_c_header(
                         self.sdram.controller.settings.phy,
                         self.sdram.controller.settings.timing)
        tools.write_to_file(os.path.join("software/generated/sdram_phy.h"), phy_header)


def main():
    platform = Platform()
    soc = USBSnifferSoC(platform, with_loopback=False, with_analyzer=False)
    builder = Builder(soc, output_dir="build", csr_csv="test/csr.csv")
    vns = builder.build()
    soc.do_exit(vns)
    soc.generate_software_header()


if __name__ == "__main__":
    main()
