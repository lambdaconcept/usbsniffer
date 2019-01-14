#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#define CSR_ACCESSORS_DEFINED
#include "generated/csr.h"

extern uint32_t eb_read_reg32(int fd, uint32_t addr);
extern void eb_write_reg32(int fd, uint32_t addr, uint32_t val);

uint8_t ulpi0_read_reg(int fd, uint8_t addr)
{
    eb_write_reg32(fd, CSR_ULPI_CORE0_REG_ADR_ADDR, addr);
    eb_write_reg32(fd, CSR_ULPI_CORE0_REG_READ_ADDR, 1);
    while(!eb_read_reg32(fd, CSR_ULPI_CORE0_REG_DONE_ADDR));
    return eb_read_reg32(fd, CSR_ULPI_CORE0_REG_DAT_R_ADDR);
}

uint8_t ulpi1_read_reg(int fd, uint8_t addr)
{
    eb_write_reg32(fd, CSR_ULPI_CORE1_REG_ADR_ADDR, addr);
    eb_write_reg32(fd, CSR_ULPI_CORE1_REG_READ_ADDR, 1);
    while(!eb_read_reg32(fd, CSR_ULPI_CORE1_REG_DONE_ADDR));
    return eb_read_reg32(fd, CSR_ULPI_CORE1_REG_DAT_R_ADDR);
}

uint8_t ulpi_read_reg(int fd, uint8_t addr, int num)
{
    if (num)
        return ulpi1_read_reg(fd, addr);
    else
        return ulpi0_read_reg(fd, addr);
}

void ulpi0_write_reg(int fd, uint8_t addr, uint8_t val)
{
    eb_write_reg32(fd, CSR_ULPI_CORE0_REG_ADR_ADDR, addr);
    eb_write_reg32(fd, CSR_ULPI_CORE0_REG_DAT_W_ADDR, val);
    eb_write_reg32(fd, CSR_ULPI_CORE0_REG_WRITE_ADDR, 1);
    while(!eb_read_reg32(fd, CSR_ULPI_CORE0_REG_DONE_ADDR));
}

void ulpi1_write_reg(int fd, uint8_t addr, uint8_t val)
{
    eb_write_reg32(fd, CSR_ULPI_CORE1_REG_ADR_ADDR, addr);
    eb_write_reg32(fd, CSR_ULPI_CORE1_REG_DAT_W_ADDR, val);
    eb_write_reg32(fd, CSR_ULPI_CORE1_REG_WRITE_ADDR, 1);
    while(!eb_read_reg32(fd, CSR_ULPI_CORE1_REG_DONE_ADDR));
}

void ulpi_write_reg(int fd, uint8_t addr, uint8_t val, int num)
{
    if (num)
        ulpi1_write_reg(fd, addr, val);
    else
        ulpi0_write_reg(fd, addr, val);
}

void ulpi0_reset(int fd, uint32_t val)
{
    eb_write_reg32(fd, CSR_ULPI_PHY0_ULPI_PHY_RESET_ADDR, val);
}

void ulpi1_reset(int fd, uint32_t val)
{
    eb_write_reg32(fd, CSR_ULPI_PHY1_ULPI_PHY_RESET_ADDR, val);
}

void ulpi_reset(int fd, uint32_t val, int num)
{
    if (num)
        ulpi1_reset(fd, val);
    else
        ulpi0_reset(fd, val);
}

void ulpi_dump(int fd, int num)
{
    int i;
    printf("Registers:\n");
    for(i=0; i< 0x19; i++)
        printf("Reg %02x -> %02x\n", i, ulpi_read_reg(fd, i, num));
    printf("\n");
}
