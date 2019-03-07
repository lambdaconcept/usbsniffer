#!/usr/bin/env python
# -*- coding: utf-8 -*-

from migen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *


# this module implements the format description from
# https://github.com/vpelletier/ITI1480A-linux/blob/master/iti1480a/parser.py#L124


PAYLOAD_NONE  = 0
PAYLOAD_EVENT = 1
PAYLOAD_DATA  = 2
PAYLOAD_RXCMD = 3

EVENT_START     = 0xe0
EVENT_STOP      = 0xf1


class ITITime(Module, AutoCSR):
    # XXX maybe run this in ULPI clock domain
    def __init__(self):
        self.reset = CSR()

        self.diff = Signal(28)      # output, time increment
        self.len = Signal(2)        # output, time increment length
        self.next = Signal()        # input, set 1 to reset time increment

        self.overflow = Signal()    # output, 1 indicates increment overflow
        self.clear = Signal()       # input, set 1 to clear overflow

        # # #

        self.sync += [
            If(self.reset.re,
                self.diff.eq(0),
                self.overflow.eq(0),
            ).Else(
                If(self.next,
                    self.diff.eq(0),
                    self.overflow.eq(0),
                ).Else(
                    self.diff.eq(self.diff + 1),
                    If(self.diff == (2**28) - 1,
                        # max value reached, trigger overflow
                        self.overflow.eq(1),
                    ).Elif(self.clear,
                        # acknowledge overflow, clear it
                        self.overflow.eq(0),
                    ),
                ),
            ),
        ]

        self.comb += [
            # how many more bytes are required to send the full time increment
            If(self.diff > (2**20 - 1),
                self.len.eq(3),
            ).Elif(self.diff > (2**12 - 1),
                self.len.eq(2),
            ).Elif(self.diff > (2**4 - 1),
                self.len.eq(1),
            ).Else(
                self.len.eq(0),
            ),
        ]


class ITIEvent(Module, AutoCSR):
    def __init__(self):
        self.event = CSR(8)

        self.data = data = Signal.like(self.event.r)
        self.new = new = Signal()
        self.ack = ack = Signal()

        # # #

        self.sync += [
            If(self.event.re,
                data.eq(self.event.r),
                new.eq(1),
            ).Elif(~self.event.re & ack,
                new.eq(0),
            )
        ]


class ITIPacker(Module, AutoCSR):
    def __init__(self):
        self.sink = sink = stream.Endpoint([('data', 8), ('cmd', 1)])
        self.source = source = stream.Endpoint([("data", 8)])

        # # #

        self.submodules.time = ITITime()
        self.submodules.ev = ITIEvent()

        payload_type = Signal(2)
        payload = Signal.like(sink.data)
        diff = Signal.like(self.time.diff)
        length = Signal.like(self.time.len)

        fsm = FSM()
        self.submodules.fsm = fsm

        fsm.act("IDLE",
            If(self.time.overflow,

                # priority to overflow event
                NextValue(payload_type, PAYLOAD_NONE),
                NextValue(diff, 2**28 - 1), # max value
                NextValue(length, 3), # max length
                self.time.clear.eq(1),

                NextState("HEADER"),

            ).Elif(self.ev.new,

                # store and ack event
                NextValue(payload, self.ev.data),
                NextValue(payload_type, PAYLOAD_EVENT),
                self.ev.ack.eq(1),

                # fetch time increment
                NextValue(diff, self.time.diff),
                NextValue(length, self.time.len),
                self.time.next.eq(1),

                NextState("HEADER"),

            ).Elif(sink.valid,

                # store payload and ack stream
                sink.ready.eq(1),
                NextValue(payload, sink.data),

                If(sink.cmd,
                    NextValue(payload_type, PAYLOAD_RXCMD),
                ).Else(
                    NextValue(payload_type, PAYLOAD_DATA),
                ),

                # fetch time increment
                NextValue(diff, self.time.diff),
                NextValue(length, self.time.len),
                self.time.next.eq(1),

                NextState("HEADER"),
            ),
        )

        fsm.act("HEADER",

            # send header byte
            source.data.eq(Cat(diff[0:4], length, payload_type)),
            source.valid.eq(1),

            If(source.ready,
                If(length > 0,
                    NextValue(diff, diff >> 4),
                    NextState("TIMESTAMP"),
                ).Else(
                    If(payload_type != PAYLOAD_NONE,
                        NextState("PAYLOAD"),
                    ).Else(
                        NextState("IDLE"),
                    ),
                ),
            ),
        )

        fsm.act("TIMESTAMP",

            # send additional timestamp bytes
            source.data.eq(diff[0:8]),
            source.valid.eq(1),

            If(source.ready,
                If(length > 1,
                    NextValue(diff, diff >> 8),
                    NextValue(length, length - 1),
                ).Else(
                    If(payload_type != PAYLOAD_NONE,
                        NextState("PAYLOAD"),
                    ).Else(
                        NextState("IDLE"),
                    ),
                )
            ),
        )

        fsm.act("PAYLOAD",

            # send payload byte
            source.data.eq(payload),
            source.valid.eq(1),

            If(source.ready,
                NextState("IDLE"),
            ),
        )


# XXX need byte swapper ??


def tb_pack(dut):
    yield dut.source.ready.eq(1)

    it = iter([(0xa5, 0), (0xd2, 0), (0xcf, 1)])
    data, cmd = next(it)

    while True:
        yield dut.sink.data.eq(data)
        yield dut.sink.cmd.eq(cmd)
        yield dut.sink.valid.eq(1)
        yield
        if (yield dut.sink.ready):
            try:
                data, cmd = next(it)
                # simulate large time increment
                yield dut.sink.valid.eq(0)
                for i in range(100):
                    yield
                yield dut.time.diff.eq(2**28 - 10)
            except StopIteration:
                break

    yield dut.sink.valid.eq(0)
    for i in range(100):
        yield

    # simulate overflow without data
    yield dut.time.diff.eq(2**28 - 10)
    for i in range(100):
        yield

    # simulate start event
    yield dut.ev.event.r.eq(0xe0)
    yield dut.ev.event.re.eq(1)
    yield
    yield dut.ev.event.re.eq(0)
    for i in range(100):
        yield

    # simulate stop event
    yield dut.ev.event.r.eq(0xf1)
    yield dut.ev.event.re.eq(1)
    yield
    yield dut.ev.event.re.eq(0)
    for i in range(100):
        yield


def tb_time(dut):
    for i in range(2):
        yield

    # test len 0
    yield dut.next.eq(1)
    yield
    yield dut.next.eq(0)
    for i in range(9):
        yield

    # test len 1
    yield dut.next.eq(1)
    yield
    yield dut.next.eq(0)
    for i in range(2**5):
        yield

    # test len 2
    yield dut.next.eq(1)
    yield
    yield dut.next.eq(0)
    yield dut.diff.eq(2**20 - 10)
    for i in range(2**13):
        yield

    # test len 3 and overflow
    yield dut.next.eq(1)
    yield
    yield dut.next.eq(0)
    yield dut.diff.eq(2**28 - 10)
    for i in range(2**16):
        if (yield dut.overflow):
            yield dut.clear.eq(1)
        else:
            yield dut.clear.eq(0)
        yield


if __name__ == "__main__":
    # dut = ITITime()
    # run_simulation(dut, tb_time(dut), vcd_name="test/iti_time.vcd")

    dut = ITIPacker()
    run_simulation(dut, tb_pack(dut), vcd_name="test/iti_pack.vcd")
