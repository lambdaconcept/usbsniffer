#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>

#ifdef WIN32
#include "FTD3XX.h"
#include "windows/ft601.h"
#endif

#include "common/testsuite.h"

void cdelay(int val)
{
    usleep(val);
}

/* global handle used by csr read/write */
#ifdef WIN32
static FT_HANDLE _gfd;
#else
static int _gfd;
#endif

extern uint32_t eb_read_reg32(int fd, uint32_t addr);
extern void eb_write_reg32(int fd, uint32_t addr, uint32_t val);

void csr_writel(uint32_t value, uint32_t addr)
{
    eb_write_reg32(_gfd, addr, value);
}

uint32_t csr_readl(uint32_t addr)
{
    return eb_read_reg32(_gfd, addr);
}

int main(int argc, char **argv)
{
    int i;
    int ret;

#ifdef WIN32
    WSADATA wsa_data;
    WSAStartup(0x0201, &wsa_data);
#endif

    printf("USBSniffer Hardware Testsuite\n\n");

#ifdef WIN32
    ret = FT601_Open(&_gfd);
#else
    if (argc < 2) {
        printf("usage: %s /dev/ft60xx\n", argv[0]);
        exit(1);
    }
    _gfd = open(argv[1], O_RDWR, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
    ret = !(_gfd < 0);
#endif
    if (!ret) {
        printf("Open failed: device not found\n");
        return ret;
    }

    /* Check BUS  */
    check_soc_identifier(_gfd);

    /* Check both ULPI chips */
    for (i=0; i<2; i++) {
        check_ulpi_scratch(_gfd, i);
    }

    /* Check SDRAM */
    check_sdram(_gfd);

    /* Check LEDs */
    for (i=0; i<2; i++) {
        check_leds(_gfd, i);
    }

#ifdef WIN32
    FT601_Close(_gfd);
#else
    close(_gfd);
#endif
    return 0;
}
