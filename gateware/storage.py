from migen import *

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream

class OverflowMeter(Module, AutoCSR):
    def __init__(self, description):
        self.sink = sink = stream.Endpoint(description)
        self.source = source = stream.Endpoint(description)

        self.reset = CSR()
        self.count = CSRStatus(32)

        # # #

        self.comb += sink.connect(source)
        self.sync += [
            If(self.reset.re,
                self.count.status.eq(0)
            ).Elif(self.sink.valid & ~self.sink.ready,
                self.count.status.eq(self.count.status + 1)
            )
        ]
