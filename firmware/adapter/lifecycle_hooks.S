.syntax unified
.thumb
.cpu cortex-m4
.macro SAVE_CONTEXT
    push {r0-r3,r12,lr}
    sub sp, sp, #8
    mrs r2, APSR
    str r2, [sp]
.endm
.macro RESTORE_CONTEXT
    ldr r2, [sp]
    msr APSR_nzcvq, r2
    add sp, sp, #8
    pop {r0-r3,r12,lr}
.endm

.section .text.sharing_enable_hook,"ax",%progbits
.global sharing_enable_hook
.type sharing_enable_hook,%function
.thumb_func
sharing_enable_hook:
    SAVE_CONTEXT
    bl usb_lifecycle_sharing_rendered
    cmp r0,#0
    beq 1f
    RESTORE_CONTEXT
    movw r0,#0x5c40 /* displaced45f64040 at0800ef8e, after original draw */
    b.w stock_sharing_continue /*0800ef92 */
1:
    RESTORE_CONTEXT
    b.w stock_sharing_skip /*0800efa6 original POP{r4,pc}; draw already finished */
.size sharing_enable_hook,.-sharing_enable_hook

.section .text.flash_shutdown_hook,"ax",%progbits
.global flash_shutdown_hook
.type flash_shutdown_hook,%function
.thumb_func
flash_shutdown_hook:
    SAVE_CONTEXT
    bl usb_lifecycle_inhibit
    RESTORE_CONTEXT
    sub sp,sp,#0x38 /* displaced8eb045f64041 at08025e14 */
    movw r1,#0x5c40
    b.w stock_flash_shutdown_continue /*08025e1a */
.size flash_shutdown_hook,.-flash_shutdown_hook
