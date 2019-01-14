#ifndef __ULPI_H_
#define __ULPI_H_

#include <stdint.h>

#define ULPI_REG_SCRATCH 0x16

uint8_t ulpi_read_reg(int fd, uint8_t addr, int num);
void ulpi_write_reg(int fd, uint8_t addr, uint8_t val, int num);
void ulpi_reset(int fd, uint32_t val, int num);
void ulpi_dump(int fd, int num);

#endif
