#include "transport.h"

const uint8_t transport_config_descriptor[18] = {
    9,2,18,0,1,1,0,0xc0,50, /* config1, one interface; stock power fields */
    9,4,0,0,0,0xff,0,0,0    /* vendor interface0, no bulk endpoints */
};

static uint16_t get16(const uint8_t *p) {
    return (uint16_t)p[0] | (uint16_t)((uint16_t)p[1] << 8);
}

static void identity(uint8_t *p) {
    static const uint8_t source_hash[32] = {
        0x83,0x27,0x1b,0xaa,0x03,0xbc,0xbf,0x15,
        0x20,0x0c,0xfb,0x80,0xfa,0x92,0xa8,0xcd,
        0x0d,0x7c,0x37,0x88,0x9b,0x08,0x8d,0x38,
        0x20,0x98,0xdc,0xd2,0xc9,0xe0,0xd2,0xb3
    };
    for (unsigned i=0;i<64;++i) p[i]=0;
    p[0]='F';p[1]='N';p[2]='I';p[3]='1';
    p[4]=1;p[5]=64;p[6]=1;
    for (unsigned i=0;i<32;++i) p[8+i]=source_hash[i];
    uint32_t c=0xffffffffu;
    for (unsigned i=0;i<60;++i) {
        c^=p[i];
        for (unsigned b=0;b<8;++b)
            c=(c>>1)^(0xedb88320u & (0u-(c&1u)));
    }
    c=~c;
    for (unsigned i=0;i<4;++i) p[60+i]=(uint8_t)(c>>(8*i));
}

int transport_setup(transport_state *s,const transport_binding *binding,enum transport_role role,
                    const uint8_t req[8]) {
    uint8_t *p=(uint8_t *)s->reply_words;
    if (role!=TRANSPORT_TELEMETRY || binding->io.current_mode(binding->io.context)!=1)
        goto reject;
    uint16_t value=get16(req+2),index=get16(req+4),length=get16(req+6);
    if (req[0]==0xc0 && value==TRANSPORT_REQUEST_TAG && index==0 && length==64) {
        if (req[1]==TRANSPORT_GET_IDENTITY) identity(p);
        else if (req[1]==TRANSPORT_GET_PARSED) parsed_snapshot(binding->parsed,p);
        else goto reject;
        binding->io.send(binding->io.context,p,64,TRANSPORT_DATA_IN);
        return 1;
    }
    /* Only alternate setting0 on the sole vendor interface is supported. */
    if (value==0 && index==0) {
        if (req[0]==0x81 && req[1]==10 && length==1) {
            p[0]=0;p[1]=0; /* stock helper rounds odd reads up to a halfword */
            binding->io.send(binding->io.context,p,1,TRANSPORT_DATA_IN);
            return 1;
        }
        if (req[0]==0x01 && req[1]==11 && length==0) {
            binding->io.send(binding->io.context,p,0,TRANSPORT_STATUS_IN);
            return 1;
        }
    }
reject:
    binding->io.stall(binding->io.context);
    return 0;
}

transport_transition transport_plan(enum transport_role current,uint8_t mode) {
    transport_transition p={0};
    p.next_role=mode==1?TRANSPORT_TELEMETRY:
                mode==7?TRANSPORT_STOCK_SHARING:TRANSPORT_OFF;
    p.allow_stock_enable=p.next_role==TRANSPORT_STOCK_SHARING;
    if (p.next_role==current) return p;
    p.detach=current!=TRANSPORT_OFF;
    p.install_telemetry=p.next_role==TRANSPORT_TELEMETRY;
    p.restore_stock=current==TRANSPORT_TELEMETRY || p.next_role==TRANSPORT_STOCK_SHARING;
    p.reconnect_telemetry=p.next_role==TRANSPORT_TELEMETRY;
    return p;
}
