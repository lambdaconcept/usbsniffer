from litex import RemoteClient
from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver

wb = RemoteClient(port=1234)
wb.open()

identifier = ""
for i in range(0, 32):
    identifier += "%c" %wb.read(wb.bases.identifier_mem + 4*i)
print("\nSoC identifier: " + identifier)
print()

# # #

analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True)
analyzer.configure_trigger(cond={
    # "soc_sender_source_source_valid": 1,
    # "soc_sender_source_source_ready": 1,
    # "soc_sender_source_source_payload_data": 0
    "soc_ulpi_core0_source_source_valid": 1,
    "soc_ulpi_core0_source_source_ready": 1,
})
# analyzer.configure_trigger()
analyzer.configure_subsampler(1)
analyzer.run(offset=1, length=1024)
analyzer.wait_done()
analyzer.upload()
analyzer.save("dump.vcd")

# # #

wb.close()
