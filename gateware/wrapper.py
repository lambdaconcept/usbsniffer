from migen import *
from migen.genlib.misc import WaitTimer

from litex.soc.interconnect import stream

from gateware.usb import user_description as usb_description


def wrap_description(dw):
    payload_layout = [
        ("data", dw),
    ]
    return stream.EndpointDescription(payload_layout)


class WrapCore(Module):
    def __init__(self, usb_core, identifier):
        self.submodules.converter = stream.StrideConverter(wrap_description(8), wrap_description(32))
        self.sink = self.converter.sink

        # # #

        self.submodules.sender = sender = WrapSender(identifier)
        usb_port = usb_core.crossbar.get_port(identifier)
        self.comb += [
            self.converter.source.connect(sender.sink),
            sender.source.connect(usb_port.sink),
        ]


class WrapSender(Module):
    def __init__(self, identifier, depth=128):
        self.submodules.buf = buf = stream.SyncFIFO(wrap_description(32), depth+1)
        self.sink = sink = buf.sink
        self.source = source = stream.Endpoint(usb_description(32))

        # # #

        count = Signal(32)

        self.submodules.timer = WaitTimer(int(1e6))

        self.comb += [
            source.dst.eq(identifier),
        ]

        fsm = FSM()
        self.submodules.fsm = fsm

        fsm.act("BUFFER",

            If(buf.level > 0,
                self.timer.wait.eq(1),
            ),

            # if buffer full or timeout elapsed
            If((buf.level >= depth) | self.timer.done,
                NextValue(count, buf.level),
                NextState("TRANSFER"),
            )
        )

        fsm.act("TRANSFER",
            source.length.eq(Cat(C(0, 2), count)),

            source.valid.eq(buf.source.valid),
            source.last.eq(count == 1),
            source.data.eq(buf.source.data),
            buf.source.ready.eq(source.ready),

            If(source.valid & source.ready,

                If(source.last,
                    # if enough data stay in transfer state
                    If(buf.level-1 >= depth,
                        NextValue(count, buf.level-1),
                    ).Else(
                        NextState("BUFFER"),
                    ),
                ).Else(
                    NextValue(count, count - 1),
                )
            ),
        )


def tb_wrap(dut):
    yield dut.source.ready.eq(1)

    val = 0xabcdef01
    it = iter([val + i for i in range(18)])
    data = next(it)

    while True:
        yield dut.sink.data.eq(data)
        yield dut.sink.valid.eq(1)
        yield
        if (yield dut.sink.ready):
            try:
                data = next(it)
                # simulate large time increment
                yield dut.sink.valid.eq(0)
                for i in range(10):
                    yield
            except StopIteration:
                break

    yield dut.sink.valid.eq(0)
    for i in range(200):
        yield


if __name__ == "__main__":
    dut = WrapSender(0)
    run_simulation(dut, tb_wrap(dut), vcd_name="test/wrapper.vcd")
