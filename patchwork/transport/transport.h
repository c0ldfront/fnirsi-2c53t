#ifndef FNIRSI_TRANSPORT_H
#define FNIRSI_TRANSPORT_H
#include <stdint.h>
#include "../payload/parsed.h"

#define TRANSPORT_GET_IDENTITY 0x50u
#define TRANSPORT_GET_PARSED 0x51u
#define TRANSPORT_REQUEST_TAG 0x3154u
#define TRANSPORT_REPLY_SIZE 64u

enum transport_role { TRANSPORT_OFF, TRANSPORT_TELEMETRY, TRANSPORT_STOCK_SHARING };
enum transport_stage { TRANSPORT_DATA_IN = 2, TRANSPORT_STATUS_IN = 4 };

/* Adapters must run serialized in the USB setup context. send receives storage
 * owned by transport_state, valid through transfer completion/new SETUP abort.
 * stage mirrors stock core+0x220. For DATA_IN adapter must set core+0x26/+0x28
 * to length and call stock send(core,0,data,length). STATUS_IN needs stage4
 * and zero-length send. No adapter is implemented here for a physical device. */
typedef struct {
    void *context;
    uint8_t (*current_mode)(void *context);
    void (*send)(void *context, const uint8_t *data, uint16_t length,
                 enum transport_stage stage);
    void (*stall)(void *context);
} transport_io;

typedef struct {
    uint32_t reply_words[16]; /* persistent 4-byte aligned storage, exactly64 bytes */
} transport_state;

/* Immutable integration bindings belong in flash (.rodata), not reserved SRAM.
 * A const pointer argument alone does not force storage placement: integration
 * must define the object itself const and verify its ELF section/address. */
typedef struct {
    const parsed_state *parsed;
    transport_io io;
} transport_binding;

_Static_assert(sizeof(transport_state)==64,"transport RAM must be exactly64 bytes");
_Static_assert(_Alignof(transport_state)>=4,"transport reply needs word alignment");
#if defined(__arm__) || defined(__thumb__)
_Static_assert(sizeof(transport_binding)==20,"unexpected ARM binding layout");
#endif

/* Original project descriptor; wrapper/pointer binding is integration's job. */
extern const uint8_t transport_config_descriptor[18];

/* Returns1 when handled,0 when stalled. Requires all io callbacks and parsed
 * state initialized, role reconciled by caller, and serialized EP0 ownership.
 * Malformed requests neither sample nor write measurement state. */
int transport_setup(transport_state *, const transport_binding *, enum transport_role,
                    const uint8_t setup[8]);

/* Pure transition PLAN, not a hardware driver. Caller must execute and verify
 * detach/quiesce/restore/reset/timing before committing next_role. */
typedef struct {
    enum transport_role next_role;
    uint8_t detach, install_telemetry, restore_stock, reconnect_telemetry;
    uint8_t allow_stock_enable;
} transport_transition;
transport_transition transport_plan(enum transport_role current, uint8_t mode);
#endif
