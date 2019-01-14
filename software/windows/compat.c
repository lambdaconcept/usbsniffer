#include <stdint.h>
#include <stdio.h>

#include "FTD3XX.h"
#include "ft601.h"

#include "common/etherbone.h"

#define FT_STREAM_PREAMBLE 0x5aa55aa5
#define FT_STREAM_HEADER_SIZE 12
#define FT_STREAM_PORTS 256

// #define DEBUG

size_t readft(FT_HANDLE fd, void *buf, size_t len)
{
    size_t toread=len;
    unsigned char *pnt=(unsigned char*)buf;
    size_t rdl;

    while(toread){
        // printf("try reading length: %d\n", toread);
        rdl = FT601_Read(fd, pnt, toread);
        if(rdl > toread)
            exit(0);

#ifdef DEBUG
    int i;
    printf("recv: ", rdl);
    for(i = 0; i < rdl; i++)
        printf("%02x", pnt[i]);
    printf("\n");
#endif

        pnt += rdl;
        toread-=rdl;
    }
    return len;
}

struct xbar_s {
    uint32_t magic;
    uint32_t streamid;
    uint32_t len;
}__attribute__((packed));

int ubar_send_packet(FT_HANDLE fd, char *buf, size_t len, int streamid)
{
    unsigned char *tosend;
    uint32_t *val;
    int i;

    tosend = malloc(len + 12);
    val = (uint32_t*)tosend;
    *(val++) = 0x5aa55aa5;// 0xa55aa55a;
    *(val++) =  streamid;
    *(val++) = len;
    memcpy(tosend+12, buf, len);

#ifdef DEBUG
    printf("send: ", len+12);
    for(i = 0; i < len+12; i++)
        printf("%02x", tosend[i]);
    printf("\n");
#endif

    FT601_Write(fd, tosend, len+12);
    return 0;
}

int ubar_recv_packet(FT_HANDLE fd, char **buf, size_t *len)
{
    struct xbar_s xbar;
    int i;
    char *tmp;
    int rdl;
    uint32_t header;

    do {
        readft(fd, &header, 4);
        // printf("magic header: %08x\n", header);
    } while(header != 0x5aa55aa5);
    xbar.magic = 0x5aa55aa5;
    readft(fd, (unsigned char*)&xbar + 4, 8);
    if(xbar.len > 32768)
    {
        exit(1);
    }
    tmp = malloc(xbar.len);

    readft(fd, tmp, xbar.len);

    *buf = tmp;
    *len = xbar.len;
    return xbar.streamid;
}

uint32_t eb_read_reg32(FT_HANDLE fd, uint32_t addr)
{
    char *buf;
    size_t len;
    uint32_t *data;
    size_t dlen;
    uint32_t ret;

    eb_make_read_pkt(addr, 1, &buf, &len);
    ubar_send_packet(fd, buf, len, 0);
    free(buf);

    ubar_recv_packet(fd, &buf, &len);
    eb_decode_rcv_pkt(buf, len, &data, &dlen);
    ret = data[0];
    free(data);
    return ret;
}

void eb_write_reg32(FT_HANDLE fd, uint32_t addr, uint32_t val)
{
    char *buf;
    size_t len;
    uint32_t *data;
    size_t dlen;
    uint32_t ret;

    eb_make_write_pkt(addr, &val, 1, &buf, &len);
    ubar_send_packet(fd, buf, len, 0);
    free(buf);
}
