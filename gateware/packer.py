from migen import *

from litex.soc.interconnect import stream

from gateware.ulpi import ulpi_description
from gateware.usb import user_description as usb_description


def lt_description(dw):
    payload_layout = [
        ("data", dw),
    ]
    return stream.EndpointDescription(payload_layout)


class TimeStamp(Module):
    def __init__(self):
        self.o = Signal(32)

        self.sync += [
            self.o.eq(self.o + 1),
        ]


class LTCore(Module):
    def __init__(self, usb_core, identifier):
        self.submodules.sender = sender = LTSender(identifier)
        usb_port = usb_core.crossbar.get_port(identifier)
        self.comb += [
            sender.source.connect(usb_port.sink),
        ]


class LTSender(Module):
    def __init__(self, identifier):
        self.sink = sink = stream.Endpoint(lt_description(32))
        self.source = source = stream.Endpoint(usb_description(32))

        # # #

        # Description sink
        #   Length:     32 bits
        #   Timestamp:  32 bits
        #   Data

        update = Signal()
        length = Signal(32)
        newlength = Signal(32)
        self.comb += [
            # align to next dword (mask +4)
            # +4 for header: length
            # +4 for header: timestamp
            newlength.eq(((sink.data-1) & 0xfffffffc) + 4 + 4 + 4)
        ]

        self.sync += [
            If(update,
                length.eq(newlength),
            ),
        ]

        self.comb += [
            source.dst.eq(identifier),

            If(sink.valid & sink.first,
                update.eq(1),
                source.length.eq(newlength),
            ).Else(
                source.length.eq(length),
            ),

            source.valid.eq(sink.valid),
            source.first.eq(sink.first),
            source.last.eq(sink.last),
            source.data.eq(sink.data),
            sink.ready.eq(source.ready),
        ]


class LTPacker(Module):
    def __init__(self, depth=512):
        self.sink = sink = stream.Endpoint(ulpi_description(8))
        self.source = source = stream.Endpoint(lt_description(32))

        # # #

        # Description source
        #   Length:     32 bits
        #   Timestamp:  32 bits
        #   Data

        counter = Signal(max=depth)

        self.submodules.ts = TimeStamp()

        fifo_data = stream.SyncFIFO(ulpi_description(8), depth)
        fifo_len = stream.SyncFIFO([("length", len(counter)+1)], depth)

        converter = stream.StrideConverter(ulpi_description(8), lt_description(32))

        self.submodules += [
            fifo_data,
            fifo_len,
            converter,
        ]

        self.comb += [
            sink.connect(fifo_data.sink),
            fifo_data.source.connect(converter.sink),
        ]

        self.comb += [
            If(sink.valid & sink.ready,
                If(sink.last,
                    fifo_len.sink.valid.eq(1),
                    fifo_len.sink.length.eq(counter + 1),
                ),
            ),
        ]

        self.sync += [
            If(sink.valid & sink.ready,
                If(sink.last,
                    counter.eq(0),
                ).Else(
                    counter.eq(counter + 1),
                ),
            )
        ]

        self.submodules.fsm = fsm = FSM()
        fsm.act("LENGTH",
            If(fifo_len.source.valid,
                source.valid.eq(1),
                source.first.eq(1),
                source.data.eq(fifo_len.source.length),

                If(source.ready,
                    fifo_len.source.ready.eq(1),
                    NextState("TIMESTAMP"),
                ),
            )
        )

        fsm.act("TIMESTAMP",
            source.valid.eq(1),
            source.data.eq(self.ts.o),

            If(source.ready,
                NextState("DATA"),
            ),
        )

        fsm.act("DATA",
            source.valid.eq(converter.source.valid),
            source.data.eq(converter.source.data),
            source.last.eq(converter.source.last),
            converter.source.ready.eq(source.ready),

            If(source.ready & source.valid & source.last,
                NextState("LENGTH"),
            ),
        )
