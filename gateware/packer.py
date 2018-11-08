from migen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.stream import EndpointDescription

from gateware.usb import user_description as usb_description

class LenTimeSender(Module):
    def __init__(self, usb_core, identifier, depth=256):
        self.submodules.packer = packer = LenTimePacker(identifier, depth=depth)
        self.sink = packer.sink
        usb_port = usb_core.crossbar.get_port(identifier)
        self.comb += [
            packer.source.connect(usb_port.sink),
        ]

class LenTimePacker(Module):
    def __init__(self, identifier, depth=256):
        self.source = stream.Endpoint(usb_description(32))
        self.submodules.converter = converter = stream.StrideConverter([("data", 8)], [("data", 32)])
        self.sink = self.converter.sink

        # # #

        counter = Signal(max=depth)
        lastlen = Signal(32)
        timer = Signal(32)

        self.sync += timer.eq(timer + 1)

        self.submodules.fifo_data = stream.SyncFIFO([("data", 32)], depth)
        self.submodules.fifo_len = stream.SyncFIFO([("val", 32)], len(counter))

        self.comb += self.converter.source.connect(self.fifo_data.sink)

        self.sync += [
            If(self.sink.valid & self.sink.ready,
                If(self.sink.last,
                    counter.eq(0)
                ).Else(
                    counter.eq(counter + 1)
                )
            )
        ]

        self.comb += [
            #   If(self.sink.valid & self.sink.ready & self.sink.last,
            If(self.sink.valid & self.sink.last,
                self.fifo_len.sink.valid.eq(1),
                self.fifo_len.sink.val.eq(counter + 1),
            )
        ]

        fsm = FSM()
        self.submodules += fsm

        self.comb += self.source.dst.eq(identifier)

        fsm.act("IDLE",
            If(self.fifo_len.level,
                #self.source.data.eq(self.fifo_len.source.val),
                self.source.data.eq(self.fifo_len.source.val),
                self.source.valid.eq(self.fifo_len.source.valid),
                self.source.first.eq(1),
                self.source.length.eq((self.fifo_len.source.val & 0xfffffffc) + 12),
                NextValue(lastlen, (self.fifo_len.source.val & 0xfffffffc) + 12),
                self.fifo_len.source.ready.eq(self.source.ready)
            ),
            If(self.source.ready & self.fifo_len.source.valid,
                NextState("TIMESTAMP")
            )
        )

        fsm.act("TIMESTAMP",
            self.source.length.eq(lastlen),
            self.source.data.eq(timer),
            self.source.valid.eq(1),
            If(self.source.ready,
                NextState("DATA")
            )
        )

        fsm.act("DATA",
            self.source.length.eq(lastlen),
            self.source.data.eq(self.fifo_data.source.data),
            self.source.valid.eq(self.fifo_data.source.valid),
            self.source.last.eq(self.fifo_data.source.last),
            self.fifo_data.source.ready.eq(self.source.ready),
            If(self.source.ready & self.fifo_data.source.valid & self.fifo_data.source.last,
                NextState("IDLE")
            )
        )
