INCLUDES=-I.

CC_WIN=i686-w64-mingw32.static-gcc
INCLUDES_WIN=-I./windows/FTD3XXLibrary
LIBS_WIN=windows/FTD3XXLibrary/Win32/FTD3XX.lib

CC_LINUX=gcc

all: build_windows build_linux

build_windows: build_windows_test

build_linux: build_linux_test

build_windows_test:
	$(CC_WIN) windows/*.c common/*.c -o test_hw.exe $(INCLUDES) $(INCLUDES_WIN) -lws2_32 $(LIBS_WIN)
	cp windows/FTD3XXLibrary/Win32/FTD3XX.dll FTD3XX.dll

build_linux_test:
	$(CC_LINUX) linux/*.c common/*.c -o test_hw $(INCLUDES)
