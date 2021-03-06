# Copyright (C) 2019 / LambdaConcept  / po@lambdaconcept.com
from migen import *

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream

def ulpi_description(dw):
    payload_layout = [
        ("data", dw),
    ]
    return stream.EndpointDescription(payload_layout)

def ulpi_cmd_description(dw, cmddw):
    payload_layout = [
        ("data", dw),
        ("cmd", cmddw),
    ]
    return stream.EndpointDescription(payload_layout)

class ULPIPHY(Module, AutoCSR):
    def __init__(self, pads, cd="ulpi"):
        self.submodules.ulpi_phy = ClockDomainsRenamer(cd)(ULPIPHYS7(pads))

        fifo_sink = stream.AsyncFIFO(self.ulpi_phy.sink.description, 4)
        self.submodules.fifo_sink = ClockDomainsRenamer({"write": "sys", "read": cd})(fifo_sink)

        fifo_source = stream.AsyncFIFO(self.ulpi_phy.source.description, 4)
        self.submodules.fifo_source = ClockDomainsRenamer({"write": cd, "read": "sys"})(fifo_source)

        self.sink = self.fifo_sink.sink
        self.source = self.fifo_source.source

        # # #

        self.rx_fifo = self.ulpi_phy.rx_fifo

        self.comb += [
            self.fifo_sink.source.connect(self.ulpi_phy.sink),
            self.ulpi_phy.source.connect(self.fifo_source.sink),
        ]

class ULPIPHYS7(Module, AutoCSR):
    # assuming 60MHz sys_clk
    def __init__(self, pads):
        self.sink   = sink = stream.Endpoint([('data', 8)])
        self.source = source = stream.Endpoint([('data', 8), ('cmd', 1)])

        self.reset = CSRStorage(reset=1)

        self.rx_count_reset = CSR()
        self.rx_count = CSRStatus(32)
        self.tx_count_reset = CSR()
        self.tx_count = CSRStatus(32)

        # # #

        self.submodules.tx_fifo = tx_fifo = stream.SyncFIFO(self.sink.description, 4)
        self.submodules.rx_fifo = rx_fifo = stream.SyncFIFO(self.source.description, 4)
        self.comb += [
            sink.connect(tx_fifo.sink),
            rx_fifo.source.connect(source),
        ]
        self.sync += [
            # rx count
            If(self.rx_count_reset.re,
                self.rx_count.status.eq(0)
            ).Elif(source.valid, # & source.ready not needed
                self.rx_count.status.eq(self.rx_count.status + 1)
            ),
            # tx count
            If(self.tx_count_reset.re,
                self.tx_count.status.eq(0)
            ).Elif(sink.valid & sink.ready,
                self.tx_count.status.eq(self.tx_count.status + 1)
            )
        ]

        self.data_t = TSTriple(8)
        self.specials += self.data_t.get_tristate(pads.data)
        last = Signal()
        odir = Signal()

        data_i = Signal(8)

        for i in range(8):
            self.specials += Instance("IDDR",
                p_DDR_CLK_EDGE="SAME_EDGE", p_INIT_Q1=0, p_INIT_Q2=0, p_SRTYPE="ASYNC",
                i_C=ClockSignal("sys"),
                i_CE=1, i_S=0, i_R=0,
                i_D=self.data_t.i[i], o_Q1=Signal(), o_Q2=data_i[i]
            )

        if hasattr(pads, "rst"):
            self.comb += pads.rst.eq(self.reset.storage)
        if hasattr(pads, "rst_n"):
            self.comb += pads.rst_n.eq(~self.reset.storage)

        self.comb += [
            self.data_t.oe.eq(~odir),
            If(tx_fifo.source.valid,
                self.data_t.o.eq(tx_fifo.source.data),
            ).Else(
                self.data_t.o.eq(0)
            ),
            tx_fifo.source.ready.eq(~pads.dir & pads.nxt),
            If(~pads.dir,
                pads.stp.eq(last),
            ),
            rx_fifo.sink.last.eq(odir & ~pads.dir),
            rx_fifo.sink.data.eq(data_i),
        ]

        self.sync += [
            If(pads.nxt,
                last.eq(tx_fifo.source.last),
            ).Else(
                last.eq(0)
            ),
            odir.eq(pads.dir),
            rx_fifo.sink.cmd.eq(~pads.nxt),
            rx_fifo.sink.valid.eq(odir & pads.dir)
        ]

class ULPIEncoder(Module, AutoCSR):
    def __init__(self):
        self.sink = sink = stream.Endpoint(ulpi_description(8))
        self.source = source = stream.Endpoint(ulpi_description(8))

        # # #

        tx_cmd = Signal(8)

        self.comb += [
            tx_cmd[6:8].eq(0x01), # Transmit
            tx_cmd[4:6].eq(0),
            tx_cmd[0:4].eq(sink.data[0:4]), # PID
        ]

        self.comb += [
            source.valid.eq(sink.valid),
            source.first.eq(sink.first),
            If(sink.first,
                source.data.eq(tx_cmd),
            ).Else(
                source.data.eq(sink.data),
            ),
            source.last.eq(sink.last),
            sink.ready.eq(source.ready),
        ]

class ULPICore(Module, AutoCSR):
    def __init__(self, phy):
        self.submodules.encoder = ULPIEncoder()
        self.sink = self.encoder.sink
        self.source = source = stream.Endpoint([('data', 8), ('cmd', 1)])

        self.reg_adr = CSRStorage(6)
        self.reg_dat_r = CSRStatus(8)
        self.reg_dat_w = CSRStorage(8)
        self.reg_write = CSR()
        self.reg_read = CSR()
        self.reg_done = CSRStatus()

        self.enable_source = CSRStorage()

        # # #

        flushcnt = Signal(max=phy.rx_fifo.depth)

        self.submodules.fsm = fsm = FSM()
        fsm.act("IDLE",
            self.reg_done.status.eq(1),
            If(self.reg_write.re,
                NextState("WRITE_REG_ADR")
            ).Elif(self.reg_read.re,
                NextState("READ_FLUSH")
            ).Else(
                If(self.enable_source.storage,
                    phy.source.connect(source),
                ).Else(
                    phy.source.ready.eq(1), # drop
                ),
                self.encoder.source.connect(phy.sink),
            ),
            NextValue(flushcnt, 0)
        )

        fsm.act("WRITE_REG_ADR",
            phy.sink.valid.eq(1),
            phy.sink.data.eq(0x80 | self.reg_adr.storage),
            If(phy.sink.ready,
                NextState("WRITE_REG_DAT")
            )
        )

        fsm.act("WRITE_REG_DAT",
            phy.sink.valid.eq(1),
            phy.sink.last.eq(1),
            phy.sink.data.eq(self.reg_dat_w.storage),
            If(phy.sink.ready,
                NextState("IDLE")
            )
        )

        fsm.act("READ_FLUSH",
            phy.source.ready.eq(1),
            If(flushcnt == (phy.rx_fifo.depth - 1),
                NextState("READ_REG_ADR")
            ).Else(
                NextValue(flushcnt, flushcnt + 1)
            )
        )

        fsm.act("READ_REG_ADR",
            phy.sink.valid.eq(1),
            phy.sink.data.eq(0xc0 | self.reg_adr.storage),
            If(phy.sink.ready,
                NextState("READ_REG_DAT")
            )
        )

        fsm.act("READ_REG_DAT",
            phy.source.ready.eq(1),
            If(phy.source.valid,
                NextValue(self.reg_dat_r.status, phy.source.data),
                NextState("IDLE")
            )
        )
