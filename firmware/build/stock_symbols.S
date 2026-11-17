/* Known stock entry points typed as Thumb functions, not generic absolute data.
 * Version pin is enforced before linking. No stock code copied here. */
.syntax unified
.thumb
.cpu cortex-m4
.global stock_parser_wait
.type stock_parser_wait,%function
.thumb_set stock_parser_wait,0x0803f9d5
.global stock_numeric_continue
.type stock_numeric_continue,%function
.thumb_set stock_numeric_continue,0x08039463
.section .note.GNU-stack,"",%progbits

.global stock_usb_send
.type stock_usb_send,%function
.thumb_set stock_usb_send,0x0803e4e1
.global stock_usb_class_setup
.type stock_usb_class_setup,%function
.thumb_set stock_usb_class_setup,0x0802ce3d
.global stock_key_continue
.type stock_key_continue,%function
.thumb_set stock_key_continue,0x0803b511

.global stock_task_delay
.type stock_task_delay,%function
.thumb_set stock_task_delay,0x0803e9bd
.global stock_usb_reset
.type stock_usb_reset,%function
.thumb_set stock_usb_reset,0x0803dfbd


.global stock_sharing_continue
.type stock_sharing_continue,%function
.thumb_set stock_sharing_continue,0x0800ef93

.global stock_flash_shutdown_continue
.type stock_flash_shutdown_continue,%function
.thumb_set stock_flash_shutdown_continue,0x08025e1b

.global stock_display_receive
.type stock_display_receive,%function
.thumb_set stock_display_receive,0x0803f805

.global stock_sharing_skip
.type stock_sharing_skip,%function
.thumb_set stock_sharing_skip,0x0800efa7
