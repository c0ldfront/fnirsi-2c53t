#include "parsed.h"
_Static_assert(sizeof(parsed_state) == 32, "RAM budget mismatch");
static void barrier(void) {
#if defined(__arm__) || defined(__thumb__)
    __asm__ volatile("dmb" ::: "memory");
#else
    __asm__ volatile("" ::: "memory");
#endif
}
static void put32(uint8_t *p, uint32_t n) {
    for (unsigned i = 0; i < 4; ++i) p[i] = (uint8_t)(n >> (i * 8));
}
void parsed_publish(parsed_state *s, const volatile uint8_t stock[16],
                    uint8_t mode, uint8_t relative, uint8_t numeric_updated) {
    parsed_publish_generation(s,stock,mode,relative,numeric_updated,0);
}
void parsed_publish_generation(parsed_state *s, const volatile uint8_t stock[16],
                    uint8_t mode, uint8_t relative, uint8_t numeric_updated,
                    uint32_t generation) {
    ++s->epoch; barrier();
    for (unsigned i = 0; i < 16; ++i) s->stock[i] = stock[i];
    s->mode = mode; s->relative = relative;
    s->numeric = numeric_updated != 0; s->present = 1;
    s->generation = generation;
    ++s->samples;
    barrier(); ++s->epoch;
}
void parsed_snapshot(const parsed_state *s, uint8_t p[64]) {
    for (unsigned i = 0; i < 64; ++i) p[i] = 0;
    p[0]='F'; p[1]='N'; p[2]='P'; p[3]='1'; p[4]=1; p[5]=64;
    uint32_t before = s->epoch;
    barrier();
    if (!(before & 1u)) {
        p[7] = s->mode;
        put32(p + 8, s->samples);
        put32(p + 12, s->generation);
        for (unsigned i = 0; i < 16; ++i) p[16+i] = s->stock[i];
        p[32] = s->relative;
        if (s->present) p[6] |= 4;
        if (s->numeric) p[6] |= 1;
        if (p[7] == 1) p[6] |= 8;
        barrier();
        if (before != s->epoch) p[6] = 2;
    } else p[6] = 2;
    if (p[6] == 2)
        for (unsigned i = 7; i < 60; ++i) p[i] = 0;
    uint32_t crc = 0xffffffffu;
    for (unsigned i = 0; i < 60; ++i) {
        crc ^= p[i];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
    }
    put32(p + 60, ~crc);
}
