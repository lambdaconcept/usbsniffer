import time

from sdram_init import *

from etherbone import Etherbone, USBMux

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

def ulpi_read_reg(eb, reg):
    eb.regs.ulpi_core_reg_adr.write(reg)
    eb.regs.ulpi_core_reg_read.write(1)
    while not eb.regs.ulpi_core_reg_done.read():
        pass
    data = eb.regs.ulpi_core_reg_dat_r.read()
    print(hex(data))

def ulpi_write_reg(eb, reg, val):
    eb.regs.ulpi_core_reg_adr.write(reg)
    eb.regs.ulpi_core_reg_dat_w.write(val)
    eb.regs.ulpi_core_reg_write.write(1)
    while not eb.regs.ulpi_core_reg_done.read():
        pass

def ulpi_reset(eb, val):
    print("PHY reset")
    eb.regs.ulpi_phy_ulpi_phy_reset.write(val)

def ulpi_dump(eb):
    print("Registers:")
    for i in range(0x19):
        ulpi_read_reg(eb, i)

def ulpi_init(eb):
    ulpi_reset(eb, 1)
    time.sleep(0.5)

    ulpi_reset(eb, 0)
    time.sleep(0.1)

    ulpi_dump(eb)

    print("Config")
    ulpi_write_reg(eb, 0x0a, 0x00) # Disable 15kohms pull-down resistors
    ulpi_write_reg(eb, 0x0f, 0x1f) # clear interrupt rising
    ulpi_write_reg(eb, 0x12, 0x1f) # clear interrupt falling
    ulpi_write_reg(eb, 0x04, 0b01001000)

STREAMID_WISHBONE = 0
STREAMID_ULPI = 1

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

    eb.regs.ulpi_core_splitter_delimiter.write(0x48) # delimiter

    ulpi_init(eb)

    print("Waiting for ULPI data:")
    while True:
        data = usbmux.recv(STREAMID_ULPI)
        lt_unpack(eb, data)
