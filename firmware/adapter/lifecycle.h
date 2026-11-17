#ifndef FNIRSI_USB_LIFECYCLE_H
#define FNIRSI_USB_LIFECYCLE_H
#include "stock_adapter.h"
typedef struct {
    uint32_t initialized,last_mode,sharing_rendered,inhibited;
} usb_lifecycle_state;
_Static_assert(sizeof(usb_lifecycle_state)==16,"lifecycle RAM budget");
extern volatile usb_lifecycle_state lifecycle_state;
extern volatile uint32_t stock_scheduler_running,stock_scheduler_suspended;
extern void stock_task_delay(uint32_t ticks);
extern void stock_usb_reset(void);
extern uint32_t stock_display_receive(void *queue,void *destination,uint32_t ticks);
extern void parser_invalidate_snapshot(void);

/* Task-context display hook only. Invalid execution context leaves transport
 * unchanged; it never waits from ISR/pre-scheduler/critical-section context. */
void usb_lifecycle_reconcile(void);
uint32_t usb_lifecycle_sharing_rendered(void);
uint32_t usb_lifecycle_receive(void *queue,void *destination,uint32_t ticks);
/* Must precede stock flash-save disconnect, including during detach delay. */
void usb_lifecycle_inhibit(void);
#endif
