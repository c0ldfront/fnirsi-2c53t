#ifndef TELEMETRY_H
#define TELEMETRY_H
#include <stdint.h>

/* Protocol is a project design, not a stock FNIRSI interface. */
#define TELEMETRY_PACKET_SIZE 40u
#define TELEMETRY_VALID 1u
#define TELEMETRY_BUSY 2u
typedef struct {
    volatile uint32_t epoch;
    volatile uint32_t samples;
    volatile uint32_t rejected;
    volatile uint8_t frame[12];
} telemetry_state;

/* Single writer only; caller must initialize state to zero before enabling IRQs.
 * No USB, allocation, numeric conversion or retries in capture.
 * RAM placement and hook binding are intentionally not defined here. */
void telemetry_capture(telemetry_state *state, const volatile uint8_t frame[12]);
/* Returns a complete packet; BUSY is explicit when writer preemption prevents
 * a coherent read. Never spin waiting for a preempted interrupt to finish. */
void telemetry_snapshot(const telemetry_state *state,
                        uint8_t packet[TELEMETRY_PACKET_SIZE]);
#endif
