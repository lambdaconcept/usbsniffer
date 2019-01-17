from migen import *

from litex.soc.interconnect.csr import *

from gateware.spi import SPIMaster


class Flash(Module, AutoCSR):
    def __init__(self, pads, div=4):
        pads_i = Record([("cs_n", 1), ("clk", 1), ("mosi", 1), ("miso", 1)])
        self.submodules.spi = SPIMaster(pads_i, width=40, div=div)

        pads.vpp.reset = 1
        pads.hold.reset = 1

        self.comb += [
            pads.cs_n.eq(pads_i.cs_n),
            pads.mosi.eq(pads_i.mosi),
            pads_i.miso.eq(pads.miso)
        ]

        # we need to use STARTUPE2 to drive clk on 7-series
        self.specials += \
            Instance("STARTUPE2",
                i_CLK=0,
                i_GSR=0,
                i_GTS=0,
                i_KEYCLEARB=0,
                i_PACK=0,
                i_USRCCLKO=pads_i.clk,
                i_USRCCLKTS=0,
                i_USRDONEO=1,
                i_USRDONETS=1)
