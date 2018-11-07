import time

from etherbone import Etherbone, USBMux

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

if __name__ == '__main__':
    usbmux = USBMux("/dev/ft60x0")
    eb = Etherbone(usbmux, STREAMID_WISHBONE,
                          csr_csv="test/csr.csv", csr_data_width=8, debug=False)

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
        print(data.hex())
