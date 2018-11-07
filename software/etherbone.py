import struct

from litex.soc.tools.remote.etherbone import *
from litex.soc.tools.remote.csr_builder import CSRBuilder

class USBMux():
    def __init__(self, path):
        self.f = open(path, "r+b")
        self.magic = 0x5aa55aa5

    def send(self, streamid, packet):
        length = len(packet)
        header = struct.pack("III", self.magic, streamid, length)
        data = header + packet
        # print("send:", data.hex())
        self.f.write(data)

    def recv(self, streamid):
        data = self.f.read(12)
        magic, streamid, length = struct.unpack("III", data)
        print("Header:", hex(magic), streamid, length)
        # print(data.hex())
        packet = self.f.read(length)
        # print(packet.hex())
        return packet

class Etherbone(CSRBuilder):
    def __init__(self, io, streamid, csr_csv=None, csr_data_width=32, debug=False):
        self.io = io
        self.streamid = streamid
        if csr_csv is not None:
            CSRBuilder.__init__(self, self, csr_csv, csr_data_width)
        self.debug = debug

    def open(self):
        pass

    def close(self):
        pass

    def read(self, addr, length=None):
        length_int = 1 if length is None else length
        datas = []
        for i in range(length_int):
            record = EtherboneRecord()
            record.reads = EtherboneReads(addrs=[addr + 4*i])
            record.rcount = 1

            packet = EtherbonePacket()
            packet.records = [record]
            packet.encode()

            self.io.send(self.streamid, bytes(packet))
            data = self.io.recv(self.streamid)

            packet = EtherbonePacket(data)
            packet.decode()
            datas.append(packet.records.pop().writes.get_datas()[0])
        if self.debug:
            for i, data in enumerate(datas):
                print("read {:08x} @ {:08x}".format(data, addr + 4*i))
        return datas[0] if length is None else datas

    def write(self, addr, datas):
        datas = datas if isinstance(datas, list) else [datas]
        for i, data in enumerate(datas):
            record = EtherboneRecord()
            record.writes = EtherboneWrites(base_addr=addr + 4*i, datas=[data])
            record.wcount = 1

            packet = EtherbonePacket()
            packet.records = [record]
            packet.encode()

            self.io.send(self.streamid, bytes(packet))

            if self.debug:
                print("write {:08x} @ {:08x}".format(data, addr + 4*i))
