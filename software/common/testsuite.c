#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "ulpi.h"

#define CSR_ACCESSORS_DEFINED
#include "generated/csr.h"
#include "generated/sdram_phy.h"

extern uint32_t eb_read_reg32(int fd, uint32_t addr);
extern void eb_write_reg32(int fd, uint32_t addr, uint32_t val);

int check_soc_identifier(int fd)
{
    int i;
    char id[32 + 1];

    printf("SoC identifier:\n");
    for (i=0; i<32; i++) {
        id[i] = eb_read_reg32(fd, CSR_IDENTIFIER_MEM_BASE + 4*i);
    }
    id[i] = '\0';
    printf("\t%s\n\n", id);

    return 0;
}

int check_ulpi_scratch(int fd, int num)
{
    uint8_t reg;

    printf("ULPI %d scratch test:\n", num);

    /* reset ulpi chip */
    ulpi_reset(fd, 1, num);
    usleep(100000);

    ulpi_reset(fd, 0, num);
    usleep(100000);

    /* write some value */
    ulpi_write_reg(fd, ULPI_REG_SCRATCH, 0xc3, num);

    /* read our written value, must match */
    reg = ulpi_read_reg(fd, ULPI_REG_SCRATCH, num);
    if(reg != 0xc3)
        goto error;

    printf("\t[OK]\n\n");
    return 0;
error:
    printf("\t[ERROR]\n\n");
    return 1;
}

#define MAIN_RAM_BASE 0x40000000

int check_sdram(int fd)
{
    uint32_t i;
    uint32_t val;

    printf("Testing SDRAM write/read:\n");

    /* initialize sdram registers */
    init_sequence();

    /* calibrate */
    // XXX

    /* check write/read */
    for (i=0; i<32; i++) {
        eb_write_reg32(fd, MAIN_RAM_BASE + 4*i, i);
        val = eb_read_reg32(fd, MAIN_RAM_BASE + 4*i);
        if (val != i)
            goto error;
    }

    printf("\t[OK]\n\n");
    return 0;
error:
    printf("\t[ERROR]\n\n");
    return 1;
}

int check_leds(int fd, int num)
{
    uint32_t reg;

    printf("LED %d blink test:\n", num);

    /* Force LED blink */
    if (num)
        blinker1_forceblink_write(1);
    else
        blinker0_forceblink_write(1);

    printf("\t[Check LEDS]\n\n");

    return 0;
}
