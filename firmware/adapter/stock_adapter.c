#include "stock_adapter.h"

static uint8_t current_mode(void *context) {
    (void)context;
    return stock_mode;
}

static uint32_t read32(const uint8_t *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}

static void clear_stale_reply(void) {
    uint8_t *p=(uint8_t *)telemetry_transport_state.reply_words;
    for (unsigned i=0;i<64;++i) p[i]=0;
    p[0]='F';p[1]='N';p[2]='P';p[3]='1';p[4]=1;p[5]=64;
    uint32_t crc=0xffffffffu;
    for (unsigned i=0;i<60;++i) {
        crc^=p[i];
        for (unsigned bit=0;bit<8;++bit)
            crc=(crc>>1)^(0xedb88320u&(0u-(crc&1u)));
    }
    crc=~crc;
    for (unsigned i=0;i<4;++i) p[60+i]=(uint8_t)(crc>>(8*i));
}

static void send_reply(void *context,const uint8_t *data,uint16_t length,
                       enum transport_stage stage) {
    stock_usb_core_prefix *core=(stock_usb_core_prefix *)context;
    /* Lifecycle changes generation only with USB IRQ quiesced. Never clear or
     * publish parsed writer state from this callback. Canonical no-data reply
     * prevents an earlier meter session's snapshot being reported as fresh. */
    uint32_t generation=telemetry_generation;
    if (length==64 && data==(const uint8_t *)telemetry_transport_state.reply_words &&
        data[0]=='F' && data[1]=='N' && data[2]=='P' && data[3]=='1' &&
        ((generation&1u)!=0 || ((data[6]&4u)!=0 && read32(data+12)!=generation)))
        clear_stale_reply();
    core->control_state=(uint8_t)stage;
    if (stage==TRANSPORT_DATA_IN) {
        /* Halfword fields at +0x26/+0x28; do not cast unaligned pair to u32. */
        core->in_endpoints[0].remaining_control_length=length;
        core->in_endpoints[0].control_length=length;
    }
    stock_usb_send(core,0,data,length);
}

static void stall_reply(void *context) {
    /* Only this fixed synthetic vendor request reaches stock MSC setup. Its
     * vendor-type default branch stalls both EP0 directions. No caller input
     * or MSC class opcode is forwarded. See test_adapter.py and README. */
    static const stock_usb_setup_layout reject={0x40,0,0,0,0};
    (void)stock_usb_class_setup((stock_usb_core_prefix *)context,&reject);
}

const transport_binding adapter_binding={
    &telemetry_parsed_state,
    {(void *)&stock_usb_core,current_mode,send_reply,stall_reply}
};

uint32_t adapter_setup(stock_usb_core_prefix *core,stock_usb_setup_layout *setup) {
    if (core!=(stock_usb_core_prefix *)&stock_usb_core) return 1;
    (void)transport_setup(&telemetry_transport_state,&adapter_binding,
        (enum transport_role)telemetry_transport_role,(const uint8_t *)setup);
    /* Stock class status convention is zero even after a signaled stall. */
    return 0;
}

static uint32_t no_action(stock_usb_core_prefix *core) { (void)core;return 0; }
static uint32_t no_endpoint(stock_usb_core_prefix *core,uint8_t endpoint) {
    (void)core;(void)endpoint;return 0;
}
static uint32_t no_event(stock_usb_core_prefix *core,uint32_t event) {
    (void)core;(void)event;return 0;
}
const adapter_class_callbacks adapter_class_table={
    no_action,no_action,adapter_setup,no_action,no_action,
    no_endpoint,no_endpoint,no_action,no_event,0
};

const stock_usb_descriptor_layout adapter_configuration_wrapper={
    18,(uint32_t)(uintptr_t)transport_config_descriptor
};
static const stock_usb_descriptor_layout *configuration(void) {
    return &adapter_configuration_wrapper;
}

/* Original callback addresses from emulated startup .data, not new SDK offsets.
 * Device/product/serial identity is deliberately unchanged for now. Host cache
 * and class-binding behavior across descriptor changes remains a release gate. */
#define GETTER(addr) ((adapter_descriptor_callback)(uintptr_t)(addr))
const adapter_descriptor_callbacks adapter_descriptor_table={
    GETTER(0x080329f1u),GETTER(0x08032b49u),configuration,GETTER(0x08032ad1u),
    GETTER(0x08032a89u),GETTER(0x08032a95u),GETTER(0x08032ad5u),GETTER(0x08032b4du),
    GETTER(0x080329fdu),GETTER(0x08032969u)
};
#undef GETTER

void adapter_install_tables_detached(void) {
    stock_usb_core.class_address=(uint32_t)(uintptr_t)&adapter_class_table;
    stock_usb_core.descriptors_address=(uint32_t)(uintptr_t)&adapter_descriptor_table;
    __asm__ volatile("dmb" ::: "memory");
}

void adapter_restore_tables_detached(void) {
    stock_usb_core.class_address=0x20000030u;
    stock_usb_core.descriptors_address=0x20000058u;
    __asm__ volatile("dmb" ::: "memory");
}
