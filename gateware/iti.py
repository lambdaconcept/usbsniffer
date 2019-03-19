#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2019 / LambdaConcept  / po@lambdaconcept.com
# Copyright (C) 2019 / LambdaConcept  / ramtin@lambdaconcept.com

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
        self.enable = CSRStorage()

        self.diff = Signal(28)      # output, time increment
        self.len = Signal(2)        # output, time increment length
        self.next = Signal()        # input, set 1 to reset time increment

        self.overflow = Signal()    # output, 1 indicates increment overflow
        self.clear = Signal()       # input, set 1 to clear overflow

        # # #

        self.sync += [
            If(~self.enable.storage,
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
        self.source = source = stream.Endpoint([("data", 40), ("len", 2)])

        # # #

        self.submodules.time = ITITime()
        self.submodules.ev = ITIEvent()

        payload_type = Signal(2)
        payload = Signal.like(sink.data)
        diff = Signal.like(self.time.diff)
        length = Signal.like(self.time.len)

        self.comb += [
            If(self.time.overflow,

                # priority to overflow
                payload.eq(0),
                payload_type.eq(PAYLOAD_NONE),
                diff.eq(2**28 - 1), # max value
                length.eq(3), # max length

                # stream out
                source.valid.eq(1),
                If(source.ready,
                    self.time.clear.eq(1),
                ),

            ).Elif(self.ev.new,

                # received event
                payload.eq(self.ev.data),
                payload_type.eq(PAYLOAD_EVENT),

                # fetch time increment
                diff.eq(self.time.diff),
                length.eq(self.time.len),
                If(source.ready,
                    self.time.next.eq(1),
                ),

                # stream out
                source.valid.eq(1),
                If(source.ready,
                    self.ev.ack.eq(1),
                ),

            ).Elif(sink.valid,

                # rxcmd or data
                payload.eq(sink.data),
                If(sink.cmd,
                    payload_type.eq(PAYLOAD_RXCMD),
                ).Else(
                    payload_type.eq(PAYLOAD_DATA),
                ),

                # fetch time increment
                diff.eq(self.time.diff),
                length.eq(self.time.len),
                If(source.ready,
                    self.time.next.eq(1),
                ),

                # stream out
                source.valid.eq(1),
                If(source.ready,
                    sink.ready.eq(1),
                ),
            )
        ]

        self.comb += [
            # header
            source.data[0:8].eq(Cat(diff[0:4], length, payload_type)),

            # additional timestamp
            If(length == 3,
                source.data[24:32].eq(diff[20:28]),
                source.data[16:24].eq(diff[12:20]),
                source.data[ 8:16].eq(diff[ 4:12]),
            ).Elif(length == 2,
                source.data[16:24].eq(diff[12:20]),
                source.data[ 8:16].eq(diff[ 4:12]),
            ).Elif(length == 1,
                source.data[ 8:16].eq(diff[ 4:12]),
            ).Else(
                # no timestamp
            ),

            # payload
            If(length == 3,
                source.data[32:40].eq(payload),
            ).Elif(length == 2,
                source.data[24:32].eq(payload),
            ).Elif(length == 1,
                source.data[16:24].eq(payload),
            ).Else(
                source.data[ 8:16].eq(payload),
            ),

            # length (-2 to keep value on 2 bits)
            If(payload_type == PAYLOAD_NONE,
                # 1 byte header + length bytes timestamp
                source.len.eq(1 + length - 2),
            ).Else(
                # 1 byte header + length bytes timestamp + 1 byte payload
                source.len.eq(1 + length + 1 - 2),
            ),
        ]


class ITIPattern(Module):
    def __init__(self, pattern, length, repeat=1):
        """ This module generates a start pattern.
        It is used by the software to realign its decoding in case the FIFO
        is flushed or corrupted after capture start / stop.
        """
        self.source = source = stream.Endpoint([("data", 40), ("len", 2)])

        self.start = Signal()
        self.done = Signal(reset=1)

        # # #

        assert((length >= 2) and (length <= 5))

        count = Signal(max=repeat+1)

        fsm = FSM()
        self.submodules.fsm = fsm

        fsm.act("IDLE",
            self.done.eq(1),
            If(self.start,
                NextValue(count, repeat),
                NextState("PATTERN"),
            ),
        )

        fsm.act("PATTERN",
            source.data.eq(pattern),
            source.len.eq(length - 2),
            source.valid.eq(1),
            If(source.ready,
                NextValue(count, count - 1),
                If(count == 1,
                    NextState("IDLE"),
                ),
            ),
        )


@ResetInserter()
class ITICore(Module, AutoCSR):
    def __init__(self):
        self.sink = sink = stream.Endpoint([('data', 8), ('cmd', 1)])
        self.source = source = stream.Endpoint([("data", 40), ("len", 2)])

        self.start_pattern = CSR()

        # # #

        self.submodules.pattern = ITIPattern(0xe00050, 3, 4)
        self.submodules.packer = ITIPacker()

        self.comb += [
            self.pattern.start.eq(self.start_pattern.re),

            # Mux sources with priority to pattern generator
            If(self.pattern.source.valid,
                self.pattern.source.connect(source),
            ).Else(
                self.sink.connect(self.packer.sink),
                self.packer.source.connect(source),
            )
        ]


@ResetInserter()
class Conv4032(Module):
    def __init__(self):
        self.sink = sink = stream.Endpoint([('data', 40), ('len', 2)])
        self.source = source = stream.Endpoint([('data', 32)])

        tmp = Signal(32)
        remain = Signal(2)
        cases_comb = {}
        send_next = Signal()
        valid = Signal()

        for i in range(16):
            a= (i & 0xc) >> 2
            b = i & 3
            c = a+b+2

            if(a+b+2 < 4):
                d=a*8
                e=0
                v=0;
            else:
                d=0
                e=(4-a)*8
                v=1
            f = c*8
            if f > 32:
                f = f-32
            print("[{:02d}:{:02d}] <- [{:02d}:{:02d}]".format(d, f, e, (b+2)*8))
            cases_comb[i] = [
                If(self.sink.valid & self.sink.ready,
                   NextValue(remain, c&3),
                )
            ]
            if a != 0:
                cases_comb[i] += [
                    If(self.sink.valid,
                        self.source.data.eq(Cat(tmp[0:a*8], self.sink.data[0:(4-a)*8])),
                    ),
                ]
            else:
                cases_comb[i] += [
                    If(self.sink.valid,
                        self.source.data.eq(self.sink.data[0:(4-a)*8]),
                    ),
                ]

            if e != (b+2)*8:
                cases_comb[i] += [
                    If(self.sink.valid & self.sink.ready,
                       NextValue(tmp[d : f], self.sink.data[e:(b+2)*8])
                    ),
                ]

            if(v==1):
                cases_comb[i] += [valid.eq(1)]
        # case 15 brings you to sending the last tmp
        cases_comb[15] += [send_next.eq(1)]
        fsm = FSM()
        self.submodules += fsm

        fsm.act("NORMAL",
                Case(Cat(self.sink.len, remain), cases_comb),
                self.source.valid.eq(valid & self.sink.valid),
                If((self.source.valid & self.source.ready) | ~self.source.valid,
                    self.sink.ready.eq(1),
                ),
                If(send_next & self.sink.valid & self.source.valid & self.source.ready,
                   NextState("SEND_EXTRA")
                )
        )

        fsm.act("SEND_EXTRA",
                self.source.valid.eq(1),
                self.source.data.eq(tmp),
                If(self.source.ready,
                   NextState("NORMAL")
                )
        )


def tb_conv(dut):
    # yield dut.conv4032.source.ready.eq(1)

    it = iter(
        [(0xa5, 0), (0xd2, 0), (0xcf, 1)] * 50
    )
    data, cmd = next(it)

    cnt = 0
    while True:
        yield dut.packer.sink.data.eq(data)
        yield dut.packer.sink.cmd.eq(cmd)
        yield dut.packer.sink.valid.eq(1)
        # simulate not always ready
        if ((cnt % 5) == 0):
            yield dut.conv4032.source.ready.eq(1)
        else:
            yield dut.conv4032.source.ready.eq(0)
        cnt += 1
        yield
        if (yield dut.packer.sink.ready):
            try:
                data, cmd = next(it)
                # # simulate large time increment
                # yield dut.packer.sink.valid.eq(0)
                # for i in range(100):
                #     yield
                # yield dut.time.diff.eq(2**28 - 10)
            except StopIteration:
                break

    yield dut.packer.sink.valid.eq(0)
    for i in range(100):
        yield

    cnt = 0
    # simulate overflow without data
    yield dut.packer.time.diff.eq(2**28 - 10)
    for i in range(100):
        # simulate not always ready
        if ((cnt % 6) == 0):
            yield dut.conv4032.source.ready.eq(1)
        else:
            yield dut.conv4032.source.ready.eq(0)
        cnt += 1
        yield

    cnt = 0
    # simulate start event
    yield dut.packer.ev.event.r.eq(0xe0)
    yield dut.packer.ev.event.re.eq(1)
    yield
    yield dut.packer.ev.event.re.eq(0)
    for i in range(100):
        # simulate not always ready
        if ((cnt % 6) == 0):
            yield dut.conv4032.source.ready.eq(1)
        else:
            yield dut.conv4032.source.ready.eq(0)
        cnt += 1
        yield

    cnt = 0
    # simulate stop event
    yield dut.packer.ev.event.r.eq(0xf1)
    yield dut.packer.ev.event.re.eq(1)
    yield
    yield dut.packer.ev.event.re.eq(0)
    for i in range(100):
        # simulate not always ready
        if ((cnt % 6) == 0):
            yield dut.conv4032.source.ready.eq(1)
        else:
            yield dut.conv4032.source.ready.eq(0)
        cnt += 1
        yield


def tb_pack(dut):
    yield dut.source.ready.eq(1)

    it = iter(
        [(0xa5, 0), (0xd2, 0), (0xcf, 1)] * 50
    )
    data, cmd = next(it)

    while True:
        yield dut.sink.data.eq(data)
        yield dut.sink.cmd.eq(cmd)
        yield dut.sink.valid.eq(1)
        yield
        if (yield dut.sink.ready):
            try:
                data, cmd = next(it)
                # # simulate large time increment
                # yield dut.sink.valid.eq(0)
                # for i in range(100):
                #     yield
                # yield dut.time.diff.eq(2**28 - 10)
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


class TopTestBench(Module):
    def __init__(self):
        self.submodules.packer = ITIPacker()
        self.submodules.conv4032 = Conv4032()
        self.comb += [
            self.packer.source.connect(self.conv4032.sink),
        ]


if __name__ == "__main__":
    # dut = ITITime()
    # run_simulation(dut, tb_time(dut), vcd_name="test/iti_time.vcd")

    # dut = ITIPacker()
    # run_simulation(dut, tb_pack(dut), vcd_name="test/iti_pack.vcd")

    dut = TopTestBench()
    run_simulation(dut, tb_conv(dut), vcd_name="test/conv4032.vcd")
