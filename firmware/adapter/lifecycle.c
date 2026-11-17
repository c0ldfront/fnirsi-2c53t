#include "lifecycle.h"

typedef struct {
    volatile uint32_t endpoint[8],reserved0[8];
    volatile uint32_t control,status,frame,address,buffer_table;
    volatile uint32_t reserved1[3],configuration;
} usb_registers;
_Static_assert(offsetof(usb_registers,control)==0x40,"USB CTRL offset");
_Static_assert(offsetof(usb_registers,status)==0x44,"USB INTSTS offset");
_Static_assert(offsetof(usb_registers,address)==0x4c,"USB DEVADDR offset");
_Static_assert(offsetof(usb_registers,buffer_table)==0x50,"USB BUFTBL offset");
_Static_assert(offsetof(usb_registers,configuration)==0x60,"USB CFG offset");
typedef struct {
    uint8_t state,old_state,device_address,remote_wakeup,default_config,configuration;
    uint16_t configuration_status;
} usb_connection_tail;
_Static_assert(sizeof(usb_connection_tail)==8,"stock connection tail extent");
extern volatile usb_connection_tail stock_usb_connection;
#define USB_IRQ_MASK (1u<<20)
#define NVIC_SET_ENABLE (*(volatile uint32_t *)0xe000e100u)
#define NVIC_CLEAR_ENABLE (*(volatile uint32_t *)0xe000e180u)
#define NVIC_CLEAR_PENDING (*(volatile uint32_t *)0xe000e280u)

static usb_registers *registers(void) {
    return (usb_registers *)(uintptr_t)stock_usb_core.register_address;
}
static uint32_t lock(void) {
    uint32_t mask;
    __asm__ volatile("mrs %0, PRIMASK\n cpsid i" : "=r"(mask) :: "memory");
    return mask;
}
static void unlock(uint32_t mask) {
    __asm__ volatile("dsb\n isb\n msr PRIMASK, %0" :: "r"(mask) : "memory");
}
static int task_context(void) {
    uint32_t ipsr,primask,basepri,faultmask,control;
    __asm__ volatile("mrs %0, IPSR":"=r"(ipsr));
    __asm__ volatile("mrs %0, PRIMASK":"=r"(primask));
    __asm__ volatile("mrs %0, BASEPRI":"=r"(basepri));
    __asm__ volatile("mrs %0, FAULTMASK":"=r"(faultmask));
    __asm__ volatile("mrs %0, CONTROL":"=r"(control));
    return !ipsr && !primask && !basepri && !faultmask && !(control&1u) &&
           stock_scheduler_running && !stock_scheduler_suspended;
}
/* Caller holds short PRIMASK section; no wait or RTOS call here. */
static void detach(void) {
    usb_registers *r=registers();
    NVIC_CLEAR_ENABLE=USB_IRQ_MASK;
    __asm__ volatile("dsb\n isb" ::: "memory");
    r->configuration|=2u; /* remove DP pull-up before stopping PHY */
    r->control=3u;       /* DISUSB + CSRST; interrupts disabled */
    r->status=0;
    NVIC_CLEAR_PENDING=USB_IRQ_MASK;
    telemetry_transport_role=TRANSPORT_OFF;
}
static void reset_detached(int telemetry) {
    usb_registers *r=registers();
    stock_usb_reset(); /* stock endpoint RAM initialization, pinned0x0803dfbc */
    volatile uint8_t *bytes=(volatile uint8_t *)&stock_usb_core;
    for (unsigned i=0x20c;i<sizeof(stock_usb_core_prefix);++i) bytes[i]=0;
    volatile uint8_t *tail=(volatile uint8_t *)&stock_usb_connection;
    for (unsigned i=0;i<sizeof(stock_usb_connection);++i) tail[i]=0;
    stock_usb_connection.state=1;
    if (telemetry) adapter_install_tables_detached();
    else adapter_restore_tables_detached();
    /* Match stock initialization while retaining DISUSB and PUO until ready. */
    r->control=2u;
    r->status=0;
    r->buffer_table=0;
    r->address=0x80u;
    r->control=0x9e02u;
    NVIC_CLEAR_PENDING=USB_IRQ_MASK;
}

void usb_lifecycle_inhibit(void) {
    uint32_t mask=lock();
    lifecycle_state.initialized=1;
    lifecycle_state.last_mode=stock_mode;
    lifecycle_state.inhibited=1;
    telemetry_transport_role=TRANSPORT_OFF;
    parser_invalidate_snapshot();
    unlock(mask);
}

void usb_lifecycle_reconcile(void) {
    if (!task_context() || stock_usb_core.register_address!=0x40005c00u) return;
    uint32_t mask=lock();
    uint8_t mode=stock_mode;
    int mode_changed=!lifecycle_state.initialized || lifecycle_state.last_mode!=mode;
    if (mode_changed) {
        lifecycle_state.initialized=1;
        lifecycle_state.last_mode=mode;
        lifecycle_state.sharing_rendered=0;
        lifecycle_state.inhibited=0;
        parser_invalidate_snapshot();
    }
    uint32_t generation=telemetry_generation;
    uint32_t desired=mode==1?TRANSPORT_TELEMETRY:
                     mode==7?TRANSPORT_STOCK_SHARING:TRANSPORT_OFF;
    usb_registers *r=registers();
    /* Preserve an unexpected stock shutdown until an explicit mode transition.
     * The flash hook covers shutdowns occurring while already detached/waiting. */
    if (!mode_changed && telemetry_transport_role==TRANSPORT_TELEMETRY &&
        ((r->control|r->configuration)&2u)) {
        lifecycle_state.inhibited=1;
        parser_invalidate_snapshot();
        detach();
    }
    if (lifecycle_state.inhibited) { unlock(mask);return; }
    if (desired==telemetry_transport_role) { unlock(mask);return; }
    detach();
    if (desired==TRANSPORT_OFF) {
        adapter_restore_tables_detached();unlock(mask);return;
    }
    if (desired==TRANSPORT_STOCK_SHARING && !lifecycle_state.sharing_rendered) {
        unlock(mask);return;
    }
    if (generation&1u) { unlock(mask);return; }
    unlock(mask);
    /* Display task context, scheduler running, no IRQ mask/lock held. Stock
     * tick is nominal1ms;101 ticks includes >=100 complete nominal periods. */
    stock_task_delay(101);
    if (!task_context()) return;
    mask=lock();
    if (stock_mode!=mode || telemetry_generation!=generation ||
        lifecycle_state.inhibited || (telemetry_generation&1u)) {
        unlock(mask);return; /* superseded event stays detached */
    }
    reset_detached(desired==TRANSPORT_TELEMETRY);
    telemetry_transport_role=desired;
    NVIC_SET_ENABLE=USB_IRQ_MASK;
    r->control&=~2u;
    r->configuration&=~2u;
    /* Sharing can reach here only after its renderer's post-draw marker. */
    unlock(mask);
}

uint32_t usb_lifecycle_sharing_rendered(void) {
    if (!task_context() || stock_mode!=7) return 0;
    /* First reconcile detects a new mode and clears any old render marker. */
    usb_lifecycle_reconcile();
    uint32_t mask=lock();
    if (stock_mode==7) lifecycle_state.sharing_rendered=1;
    unlock(mask);
    usb_lifecycle_reconcile();
    return stock_mode==7 && !(telemetry_generation&1u) &&
           !lifecycle_state.inhibited && telemetry_transport_role==TRANSPORT_STOCK_SHARING;
}

uint32_t usb_lifecycle_receive(void *queue,void *destination,uint32_t ticks) {
    usb_lifecycle_reconcile();
    uint32_t mode=stock_mode;
    uint32_t desired=mode==1?TRANSPORT_TELEMETRY:
                     mode==7?TRANSPORT_STOCK_SHARING:TRANSPORT_OFF;
    /* Liveness: retry from this same task even if the last UI event was
     * consumed while its key callback remained odd or a detach wait expired
     * after another mode/generation change. No synthetic redraw is queued. */
    if (ticks && !lifecycle_state.inhibited && desired!=TRANSPORT_OFF &&
        telemetry_transport_role!=desired && ticks>101u) ticks=101u;
    return stock_display_receive(queue,destination,ticks);
}
