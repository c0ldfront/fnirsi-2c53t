/* V1.0.7-only offline payload layout. No claim of factory IAP acceptance. */
OUTPUT_FORMAT("elf32-littlearm")
OUTPUT_ARCH(arm)
ENTRY(parser_wait_hook)
MEMORY {
  APPEND (rx) : ORIGIN = 0x0807dd40, LENGTH = 0x22c0
  RESERVED (rw) : ORIGIN = 0x20008068, LENGTH = 128
}
SECTIONS {
  .text : ALIGN(4) {
    __payload_start = .;
    *(.text .text.*)
    *(.rodata .rodata.*)
    *(.glue_7 .glue_7t .vfp11_veneer .v4_bx)
    . = ALIGN(4);
  } > APPEND
  .ARM.extab : { *(.ARM.extab* .gnu.linkonce.armextab.*) } > APPEND
  .ARM.exidx : { *(.ARM.exidx* .gnu.linkonce.armexidx.*) } > APPEND
  .iplt : { *(.iplt) } > APPEND
  .rel.iplt : { *(.rel.iplt) } > APPEND
  __payload_end = .;
  .reservation (NOLOAD) : ALIGN(8) {
    parsed_buffer = .; . += 32;
    transport_buffer = .; . += 64;
    parser_control = .; . += 2;
    . = ALIGN(4);
    telemetry_transport_role = .; . += 4;
    telemetry_generation = .; . += 4;
    parser_iteration_generation = .; . += 4;
    lifecycle_timing = .; . += 16;
    __reservation_end = .;
  } > RESERVED
  .data : { *(.data .data.* .igot.plt) } > RESERVED
  .bss (NOLOAD) : { *(.bss .bss.* COMMON) } > RESERVED
  .ARM.attributes 0 : { *(.ARM.attributes) }
  /DISCARD/ : { *(.comment .note.GNU-stack) }
}
stock_frame = 0x20004bbd;
stock_parsed_window = 0x20000fdc;
stock_global_mode = 0x20001018;
stock_relative_mode = 0x20000fed;
ASSERT(__payload_start == 0x0807dd40, "payload append base mismatch")
ASSERT(__payload_end <= 0x08080000, "conservative append cap exceeded")
ASSERT(parsed_buffer == 0x20008068, "parsed state mismatch")
ASSERT(transport_buffer == 0x20008088, "EP0 reply mismatch")
ASSERT(parser_control == 0x200080c8, "parser controls mismatch")
ASSERT(telemetry_transport_role == 0x200080cc, "adapter role mismatch")
ASSERT(telemetry_generation == 0x200080d0, "current generation mismatch")
ASSERT(parser_iteration_generation == 0x200080d4, "iteration generation mismatch")
ASSERT(lifecycle_timing == 0x200080d8, "lifecycle timing mismatch")
ASSERT(__reservation_end == 0x200080e8, "reservation boundary mismatch")
ASSERT(SIZEOF(.iplt) == 0, "dynamic linkage not supported")
ASSERT(SIZEOF(.rel.iplt) == 0, "runtime relocations not supported")
ASSERT(SIZEOF(.data) == 0, "initialized RAM not implemented")
ASSERT(SIZEOF(.bss) == 0, "unbudgeted writable globals")

/* Integration aliases; storage is defined once above. */
telemetry_parsed_state = parsed_buffer;
telemetry_transport_state = transport_buffer;
stock_usb_core = 0x200028d0;
stock_mode = stock_global_mode;

lifecycle_state = lifecycle_timing;
stock_scheduler_running = 0x20006004;
stock_scheduler_suspended = 0x20005f90;

stock_usb_connection = 0x20002af4;
