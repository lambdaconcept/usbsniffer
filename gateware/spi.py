from migen import *

from litex.soc.interconnect.csr import *


class SPIMaster(Module, AutoCSR):
    def __init__(self, pads, width, div):
        self.pads = pads

        self._ctrl = CSR(16)
        self._status = CSRStatus(4)
        self._mosi = CSRStorage(width)
        self._miso = CSRStatus(width)

        self.irq = Signal()

        # # #

        # ctrl
        start = Signal()
        length = Signal(8)
        enable_cs = Signal()
        enable_shift = Signal()
        done = Signal()

        self.comb += [
            start.eq(self._ctrl.re & self._ctrl.r[0]),
            self._status.status.eq(done)
        ]
        self.sync += \
            If(self._ctrl.re, length.eq(self._ctrl.r[8:16]))


        # clk
        i = Signal(max=div)
        clk_en = Signal()
        set_clk = Signal()
        clr_clk = Signal()
        self.sync += [
            If(set_clk,
                pads.clk.eq(enable_cs)
            ),
            If(clr_clk,
                pads.clk.eq(0),
                i.eq(0)
            ).Else(
                i.eq(i + 1),
            )
        ]

        self.comb += [
            set_clk.eq(i == div//2-1),
            clr_clk.eq(i == div-1)
        ]

         # fsm
        count = Signal(8)
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(start,
                NextValue(count, 0),
                NextState("WAIT_CLK")
            ),
            done.eq(1)
        )
        fsm.act("WAIT_CLK",
            If(clr_clk,
                NextState("SHIFT")
            )
        )
        fsm.act("SHIFT",
            If(count == length,
                NextState("END")
            ).Elif(clr_clk,
                NextValue(count, count + 1)
            ),
            enable_cs.eq(1),
            enable_shift.eq(1)
        )
        fsm.act("END",
            If(set_clk,
                NextState("IDLE")
            ),
            enable_shift.eq(1),
            self.irq.eq(1)
        )

        # miso (captured on clk falling edge)
        miso = Signal()
        sr_miso = Signal(width)
        self.sync += \
            If(enable_shift,
                If(set_clk,
                    miso.eq(pads.miso),
                ).Elif(clr_clk,
                    sr_miso.eq(Cat(miso, sr_miso[:-1]))
                )
            )
        self.comb += self._miso.status.eq(sr_miso)

        # mosi (propagated on clk falling edge)
        mosi = Signal()
        sr_mosi = Signal(width)
        self.sync += \
            If(start,
                sr_mosi.eq(self._mosi.storage)
            ).Elif(set_clk & enable_shift,
                sr_mosi.eq(Cat(Signal(), sr_mosi[:-1]))
            ).Elif(clr_clk,
                pads.mosi.eq(sr_mosi[-1])
            )

        # cs_n
        if hasattr(pads, "cs_n"):
            self.comb += pads.cs_n.eq(~enable_cs)
