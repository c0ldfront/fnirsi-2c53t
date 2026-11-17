/* Link-time symbols are deliberately unbound until the full-image builder.
 * control[0]=previous wait succeeded; control[1]=numeric commit this iteration.
 * parsed_publish_finished bridges stock state to parsed_publish (C, pending).
 */
.syntax unified
.thumb
.cpu cortex-m4
.section .text.numeric_commit_hook,"ax",%progbits
.global numeric_commit_hook
.type numeric_commit_hook,%function
.thumb_func
numeric_commit_hook:
    /* Relocated exact stock instruction from0x0803945e. */
    strb.w r9, [r4, #0xeed]
    push {r0-r2,lr}
    mrs r2, APSR
    ldr r0, =parser_control
    movs r1, #1
    strb r1, [r0, #1]
    msr APSR_nzcvq, r2
    pop {r0-r2,lr}
    b.w stock_numeric_continue
.size numeric_commit_hook, .-numeric_commit_hook
.ltorg

.section .text.parser_wait_hook,"ax",%progbits
.global parser_wait_hook
.type parser_wait_hook,%function
.thumb_func
parser_wait_hook:
    /* Original BL ABI arguments r0 semaphore, r1 timeout. Extra saved registers
     * retain original inputs across the bounded publication callback. */
    push {r0,r1,r4,lr}
    ldr r4, =parser_control
    ldrb r0, [r4]
    cbz r0, 1f
    bl parsed_publish_finished
1:
    movs r0, #0
    strb r0, [r4]
    strb r0, [r4, #1]
    ldr r0, [sp]
    ldr r1, [sp, #4]
    bl stock_parser_wait
    ldr r2, =telemetry_generation
    ldr r2, [r2]
    ldr r3, =parser_iteration_generation
    str r2, [r3]
    /* Wait's return value must pass through unchanged. */
    cmp r0, #1
    ite eq
    moveq r1, #1
    movne r1, #0
    strb r1, [r4]
    str r0, [sp]
    pop {r0,r1,r4,pc}
.size parser_wait_hook, .-parser_wait_hook
.ltorg
