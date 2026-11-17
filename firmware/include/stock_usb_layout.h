#ifndef FNIRSI_STOCK_USB_LAYOUT_H
#define FNIRSI_STOCK_USB_LAYOUT_H
/* Original recovered-layout model, not a vendor SDK header replacement.
 * uint32_t address fields describe ARM memory and are NOT host pointers.
 * Source corroboration (relative to patchwork):
 * ../chipset-reference/artery-usb/middlewares__usbd_drivers__inc__usbd_core.h
 *   lines65-91 descriptors,96-108 class callbacks,113-138 core.
 * ../chipset-reference/artery-usb/libraries__drivers__inc__at32f403a_407_usb.h
 *   lines499-521 endpoint fields.
 * Stock observations: reports/startup-data.json, reports/usb-vector.c.txt,
 * research-usb/test_stock_send.py. Tail fields remain intentionally opaque.
 * Source edition/pin29f8bfd95b190fa38070d2e0fbbb9f3871b0b3f5 postdates stock
 * firmware; matching offsets do not prove every behavior/version identical.
 */
#include <stdint.h>
#include <stddef.h>
typedef struct {
    uint8_t number, address, direction, kind;
    uint16_t tx_address, rx_address, max_packet;
    uint8_t double_buffer, stalled;
    uint16_t status, total_length, transfer_length;
    uint32_t buffer_address;
    uint16_t last_length, remaining_control_length, control_length;
} stock_usb_endpoint_layout;
typedef struct {
    uint8_t request_type, request;
    uint16_t value, index, length;
} stock_usb_setup_layout;
typedef struct {
    uint16_t length; /* next two bytes are ABI padding, not high length bits */
    uint32_t descriptor_address;
} stock_usb_descriptor_layout;
typedef struct {
    uint32_t init, clear, setup, ep0_tx, ep0_rx, in, out, sof, event, data;
} stock_usb_class_layout;
typedef struct {
    uint32_t device, qualifier, configuration, other_speed, language;
    uint32_t manufacturer, product, serial, interface_string, configuration_string;
} stock_usb_descriptors_layout;
typedef struct {
    uint32_t register_address, class_address, descriptors_address;
    stock_usb_endpoint_layout in_endpoints[8], out_endpoints[8];
    stock_usb_setup_layout setup;
    uint8_t setup_buffer[12], control_state, speed;
    uint16_t control_length;
} stock_usb_core_prefix;
#define STOCK_OFF(type, field, expected) \
    _Static_assert(offsetof(type, field)==(expected), #type "." #field " offset")
_Static_assert(sizeof(stock_usb_endpoint_layout)==32,"endpoint stride");
_Static_assert(sizeof(stock_usb_descriptor_layout)==8,"descriptor wrapper size");
_Static_assert(sizeof(stock_usb_setup_layout)==8,"setup size");
_Static_assert(sizeof(stock_usb_class_layout)==40,"class table size");
_Static_assert(sizeof(stock_usb_descriptors_layout)==40,"descriptor table size");
STOCK_OFF(stock_usb_descriptor_layout,descriptor_address,4);
STOCK_OFF(stock_usb_core_prefix,class_address,4);
STOCK_OFF(stock_usb_core_prefix,descriptors_address,8);
STOCK_OFF(stock_usb_core_prefix,in_endpoints,0x0c);
STOCK_OFF(stock_usb_core_prefix,out_endpoints,0x10c);
STOCK_OFF(stock_usb_core_prefix,setup,0x20c);
STOCK_OFF(stock_usb_core_prefix,setup_buffer,0x214);
STOCK_OFF(stock_usb_core_prefix,control_state,0x220);
STOCK_OFF(stock_usb_endpoint_layout,buffer_address,0x14);
STOCK_OFF(stock_usb_endpoint_layout,remaining_control_length,0x1a);
STOCK_OFF(stock_usb_endpoint_layout,control_length,0x1c);
#undef STOCK_OFF
#endif
