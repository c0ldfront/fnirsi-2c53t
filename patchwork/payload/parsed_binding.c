/* Absolute symbols are supplied by a version-pinned linker script, not guessed
 * here. This translation unit has no writable-device interface. */
#include "parsed.h"
extern parsed_state parsed_buffer;
extern volatile uint8_t stock_parsed_window[16];
extern volatile uint8_t stock_global_mode, stock_relative_mode;
extern volatile uint8_t parser_control[2];
extern volatile uint32_t telemetry_generation, parser_iteration_generation;
void parser_invalidate_snapshot(void) {
    uint32_t mask;
    __asm__ volatile("mrs %0, PRIMASK\n cpsid i" : "=r"(mask) :: "memory");
    telemetry_generation+=2;
    parser_control[1]=0;
    __asm__ volatile("msr PRIMASK, %0" :: "r"(mask) : "memory");
}
/* Only the serialized key-task callback wrapper may pair these calls.
 * Odd generations mean an unfinished UI operation, including blocked callbacks.
 * These functions never wait while interrupts are masked. */
static void semantic_edge(void) {
    uint32_t mask;
    __asm__ volatile("mrs %0, PRIMASK\n cpsid i" : "=r"(mask) :: "memory");
    ++telemetry_generation;
    parser_control[1]=0;
    __asm__ volatile("msr PRIMASK, %0" :: "r"(mask) : "memory");
}
void parser_semantic_begin(void) { semantic_edge(); }
void parser_semantic_end(void) { semantic_edge(); }
void parsed_publish_finished(void) {
    uint8_t local[16], mode, relative, numeric;
    uint32_t mask, generation, iteration;
    /* Snapshot only. Never hold PRIMASK across publication, USB or a wait.
     * This excludes task/ordinary-IRQ writers, not DMA/NMI writers. It does
     * not itself establish that a mode change preceding the copy is fresh. */
    __asm__ volatile("mrs %0, PRIMASK\n cpsid i" : "=r"(mask) :: "memory");
    for (unsigned i=0;i<16;++i) local[i]=stock_parsed_window[i];
    mode=stock_global_mode; relative=stock_relative_mode; numeric=parser_control[1];
    generation=telemetry_generation; iteration=parser_iteration_generation;
    __asm__ volatile("msr PRIMASK, %0" :: "r"(mask) : "memory");
    if (!(generation & 1u) && generation == iteration)
        parsed_publish_generation(&parsed_buffer, local, mode, relative, numeric, generation);
}
