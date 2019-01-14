#include "FTD3XX.h"

int FT601_Open(FT_HANDLE *ftHandle);
int FT601_Close(FT_HANDLE ftHandle);
int FT601_Read(FT_HANDLE ftHandle, void *buf, size_t len);
int FT601_Write(FT_HANDLE ftHandle, void *buf, size_t len);
