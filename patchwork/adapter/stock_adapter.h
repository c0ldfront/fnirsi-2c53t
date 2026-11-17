#ifndef FNIRSI_STOCK_ADAPTER_H
#define FNIRSI_STOCK_ADAPTER_H
#include "../research-design-review/stock_usb_layout.h"
#include "../transport/transport.h"

/* This adapter targets the pinned 32-bit ARM image, not host-native pointers. */
_Static_assert(sizeof(void *)==4,"stock USB adapter is ARM32 only");
typedef uint32_t (*adapter_one_callback)(stock_usb_core_prefix *);
typedef uint32_t (*adapter_setup_callback)(stock_usb_core_prefix *,stock_usb_setup_layout *);
typedef uint32_t (*adapter_endpoint_callback)(stock_usb_core_prefix *,uint8_t);
typedef uint32_t (*adapter_event_callback)(stock_usb_core_prefix *,uint32_t);
typedef const stock_usb_descriptor_layout *(*adapter_descriptor_callback)(void);
typedef struct {
    adapter_one_callback init,clear;
    adapter_setup_callback setup;
    adapter_one_callback ep0_tx,ep0_rx;
    adapter_endpoint_callback in,out;
    adapter_one_callback sof;
    adapter_event_callback event;
    void *data;
} adapter_class_callbacks;
typedef struct {
    adapter_descriptor_callback device,qualifier,configuration,other_speed,language;
    adapter_descriptor_callback manufacturer,product,serial,interface_string,configuration_string;
} adapter_descriptor_callbacks;
_Static_assert(sizeof(adapter_class_callbacks)==sizeof(stock_usb_class_layout),"class ABI size");
_Static_assert(sizeof(adapter_descriptor_callbacks)==sizeof(stock_usb_descriptors_layout),"descriptor ABI size");
#define ADAPTER_OFF(a,b,field) _Static_assert(offsetof(a,field)==offsetof(b,field),#field " ABI offset")
ADAPTER_OFF(adapter_class_callbacks,stock_usb_class_layout,init);
ADAPTER_OFF(adapter_class_callbacks,stock_usb_class_layout,clear);
ADAPTER_OFF(adapter_class_callbacks,stock_usb_class_layout,setup);
ADAPTER_OFF(adapter_class_callbacks,stock_usb_class_layout,ep0_tx);
ADAPTER_OFF(adapter_class_callbacks,stock_usb_class_layout,ep0_rx);
ADAPTER_OFF(adapter_class_callbacks,stock_usb_class_layout,in);
ADAPTER_OFF(adapter_class_callbacks,stock_usb_class_layout,out);
ADAPTER_OFF(adapter_class_callbacks,stock_usb_class_layout,sof);
ADAPTER_OFF(adapter_class_callbacks,stock_usb_class_layout,event);
ADAPTER_OFF(adapter_class_callbacks,stock_usb_class_layout,data);
ADAPTER_OFF(adapter_descriptor_callbacks,stock_usb_descriptors_layout,configuration);
#undef ADAPTER_OFF

extern const adapter_class_callbacks adapter_class_table;
extern const adapter_descriptor_callbacks adapter_descriptor_table;
extern const stock_usb_descriptor_layout adapter_configuration_wrapper;
extern const transport_binding adapter_binding;

/* Integration linker resolves these; adapter defines NO new mutable RAM. */
extern volatile stock_usb_core_prefix stock_usb_core;
extern volatile uint8_t stock_mode;
extern parsed_state telemetry_parsed_state;
extern transport_state telemetry_transport_state;
extern volatile uint32_t telemetry_transport_role;
extern volatile uint32_t telemetry_generation;
extern void stock_usb_send(stock_usb_core_prefix *,uint32_t,const uint8_t *,uint32_t);
extern uint32_t stock_usb_class_setup(stock_usb_core_prefix *,const stock_usb_setup_layout *);

uint32_t adapter_setup(stock_usb_core_prefix *,stock_usb_setup_layout *);

/* PRECONDITIONS: physically detached; USB IRQ disabled/quiescent; endpoint
 * transfers stopped; caller owns lifecycle serialization. These functions only
 * replace two callback pointers. They do NOT detach/reset/delay/reconnect, set
 * role, clear pending IRQs, initialize storage, or guarantee device safety. */
void adapter_install_tables_detached(void);
void adapter_restore_tables_detached(void);
#endif
