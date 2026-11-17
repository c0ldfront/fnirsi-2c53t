#ifndef TELEMETRY_PARSED_H
#define TELEMETRY_PARSED_H
#include <stdint.h>
typedef struct {
    volatile uint32_t epoch, samples;
    volatile uint8_t stock[16];
    volatile uint8_t mode, relative, numeric, present;
    volatile uint32_t generation;
} parsed_state;
/* Call after parser/formatter completion in its sole writer task. */
void parsed_publish(parsed_state *, const volatile uint8_t stock[16],
                    uint8_t mode, uint8_t relative, uint8_t numeric_updated);
void parsed_snapshot(const parsed_state *, uint8_t packet[64]);
void parsed_publish_generation(parsed_state *, const volatile uint8_t stock[16],
                    uint8_t mode, uint8_t relative, uint8_t numeric_updated,
                    uint32_t generation);
#endif
