import time

from sdram_init import *

from etherbone import Etherbone, USBMux
from gateware.ulpi import ULPIFilter

def sdram_configure(wb):
    # software control
    wb.regs.sdram_dfii_control.write(0)

    # sdram initialization
    for i, (comment, a, ba, cmd, delay) in enumerate(init_sequence):
        print(comment)
        wb.regs.sdram_dfii_pi0_address.write(a)
        wb.regs.sdram_dfii_pi0_baddress.write(ba)
        if i < 2:
            wb.regs.sdram_dfii_control.write(cmd)
        else:
            wb.regs.sdram_dfii_pi0_command.write(cmd)
            wb.regs.sdram_dfii_pi0_command_issue.write(1)

    # hardware control
    wb.regs.sdram_dfii_control.write(dfii_control_sel)

    # configure bitslip and delay
    bitslip = 1
    delay = 18
    for module in range(2):
        wb.regs.ddrphy_dly_sel.write(1<<module)
        wb.regs.ddrphy_rdly_dq_rst.write(1)
        wb.regs.ddrphy_rdly_dq_bitslip_rst.write(1)
        for i in range(bitslip):
            wb.regs.ddrphy_rdly_dq_bitslip.write(1)
        for i in range(delay):
            wb.regs.ddrphy_rdly_dq_inc.write(1)

def ulpi0_read_reg(eb, reg):
    eb.regs.ulpi_core0_reg_adr.write(reg)
    eb.regs.ulpi_core0_reg_read.write(1)
    while not eb.regs.ulpi_core0_reg_done.read():
        pass
    return eb.regs.ulpi_core0_reg_dat_r.read()

def ulpi1_read_reg(eb, reg):
    eb.regs.ulpi_core1_reg_adr.write(reg)
    eb.regs.ulpi_core1_reg_read.write(1)
    while not eb.regs.ulpi_core1_reg_done.read():
        pass
    return eb.regs.ulpi_core1_reg_dat_r.read()

def ulpi_read_reg(eb, num, reg):
    if num == 0:
        return ulpi0_read_reg(eb, reg)
    else:
        return ulpi1_read_reg(eb, reg)

def ulpi0_write_reg(eb, reg, val):
    eb.regs.ulpi_core0_reg_adr.write(reg)
    eb.regs.ulpi_core0_reg_dat_w.write(val)
    eb.regs.ulpi_core0_reg_write.write(1)
    while not eb.regs.ulpi_core0_reg_done.read():
        pass

def ulpi1_write_reg(eb, reg, val):
    eb.regs.ulpi_core1_reg_adr.write(reg)
    eb.regs.ulpi_core1_reg_dat_w.write(val)
    eb.regs.ulpi_core1_reg_write.write(1)
    while not eb.regs.ulpi_core1_reg_done.read():
        pass

def ulpi_write_reg(eb, num, reg, val):
    if num == 0:
        ulpi0_write_reg(eb, reg, val)
    else:
        ulpi1_write_reg(eb, reg, val)

def ulpi_reset(eb, num, val):
    print("PHY reset")
    if num == 0:
        eb.regs.ulpi_phy0_ulpi_phy_reset.write(val)
    else:
        eb.regs.ulpi_phy1_ulpi_phy_reset.write(val)

def ulpi_dump(eb, num):
    print("Registers:")
    for i in range(0x19):
        reg = ulpi_read_reg(eb, num, i)
        print(hex(i), hex(reg))

def ulpi_init(eb, num):
    ulpi_reset(eb, num, 1)
    time.sleep(0.5)

    ulpi_reset(eb, num, 0)
    time.sleep(0.1)

    ulpi_dump(eb, num)

    print("Config")
    ulpi_write_reg(eb, num, 0x0a, 0x00) # Disable 15kohms pull-down resistors
    ulpi_write_reg(eb, num, 0x0f, 0x1f) # clear interrupt rising
    ulpi_write_reg(eb, num, 0x12, 0x1f) # clear interrupt falling
    ulpi_write_reg(eb, num, 0x04, 0b01001000)

STREAMID_WISHBONE = 0
STREAMID_ULPI0 = 1
STREAMID_ULPI1 = 2

def lt_unpack(eb, data):
    print(data.hex())
    length = int.from_bytes(data[0:4], "little")
    ts = int.from_bytes(data[4:12], "little")
    payload = data[12:12+length]
    print("({}, {}): {}".format(ts, length, payload.hex()))

if __name__ == '__main__':
    usbmux = USBMux("/dev/ft60x0")
    eb = Etherbone(usbmux, STREAMID_WISHBONE,
                          csr_csv="test/csr.csv", csr_data_width=8, debug=False)

    sdram_configure(eb)

    print("Testing SRAM write/read:")
    for i in range(32):
        eb.write(eb.mems.sram.base + 4*i, i)
        print("%08x" %eb.read(eb.mems.sram.base + 4*i))

    identifier = ""
    for i in range(0, 32):
        identifier += "%c" %eb.read(eb.bases.identifier_mem + 4*i)
    print("\nSoC identifier: " + identifier)
    print()

    # eb.regs.ulpi_filter_mask.write(ULPIFilter.SOF)

    eb.regs.ulpi_sw_oe_n_out.write(0)
    eb.regs.ulpi_sw_s_out.write(0)

    print("ULPI 0")
    ulpi_init(eb, 0)
    print()

    print("ULPI 1")
    ulpi_init(eb, 1)
    print()

    print("Waiting for ULPI0 data:")
    while True:
        data = usbmux.recv(STREAMID_ULPI0)
        lt_unpack(eb, data)
