/* Replace complete BLXr0 + Bloop at0803b570 (8047cde7) with B.W.
 * Single key task serializes callback pairs. No extra stack remains while
 * the original callback runs/blocks; begin/end publication is bounded.
 */
.syntax unified
.thumb
.cpu cortex-m4
.section .text.key_callback_hook,"ax",%progbits
.global key_callback_hook
.type key_callback_hook,%function
.thumb_func
key_callback_hook:
    push {r0-r3,r12,lr}
    sub sp, sp, #8
    mrs r2, APSR
    str r2, [sp]
    bl parser_semantic_begin
    ldr r2, [sp]
    msr APSR_nzcvq, r2
    add sp, sp, #8
    pop {r0-r3,r12,lr}
    blx r0
    push {r0-r3,r12,lr}
    sub sp, sp, #8
    mrs r2, APSR
    str r2, [sp]
    bl parser_semantic_end
    ldr r2, [sp]
    msr APSR_nzcvq, r2
    add sp, sp, #8
    pop {r0-r3,r12,lr}
    ldr lr, =0x0803b573
    b.w stock_key_continue
.size key_callback_hook, .-key_callback_hook
.ltorg
