/* Pi Explorer's bounded, exact scanner. AVX2 is selected at runtime; SSE2
 * machines use the portable path. Inputs and result positions are 64 bit.
 * Build with tools/build_scan.ps1. No Python API or per-digit allocations. */
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <immintrin.h>
#include <cpuid.h>

#define API __declspec(dllexport)
#define AVX __attribute__((target("avx2")))
#define INLINE_AVX static inline __attribute__((always_inline,target("avx2")))

static unsigned decode(const unsigned char *p, int mode) {
    if (!mode) return p[0];
    unsigned c=(p[0]-48)*10+p[1]-48;
    if (mode==1) return 65+c%26;
    if (mode==2) return c>=1 && c<=26 ? 64+c : 46;
    c=c*10+p[2]-48;
    return c>=32 && c<=126 ? c : 46;
}

static int equal_at(const unsigned char *data, const unsigned char *q,
                    uint64_t at, uint64_t length, int mode, unsigned step) {
    if (!mode) return !memcmp(data+at,q,(size_t)length);
    const unsigned char *p=data+at*step;
    for (uint64_t i=0;i<length;i++) if (decode(p+i*step,mode)!=q[i]) return 0;
    return 1;
}

INLINE_AVX __m256i pair_test(const unsigned char *p, unsigned ch, int mode) {
    __m256i a=_mm256_loadu_si256((const __m256i *)p);
    __m256i code=_mm256_sub_epi16(_mm256_maddubs_epi16(a,_mm256_set1_epi16(0x010a)),_mm256_set1_epi16(528));
    if (mode==1) {
        /* floor(code/26) == high16(code*2521) for the complete 0..99 domain. */
        __m256i div=_mm256_mulhi_epu16(code,_mm256_set1_epi16(2521));
        code=_mm256_sub_epi16(code,_mm256_mullo_epi16(div,_mm256_set1_epi16(26)));
        return _mm256_cmpeq_epi16(code,_mm256_set1_epi16(ch-65));
    }
    if (ch==46) return _mm256_or_si256(_mm256_cmpeq_epi16(code,_mm256_setzero_si256()),_mm256_cmpgt_epi16(code,_mm256_set1_epi16(26)));
    return _mm256_cmpeq_epi16(code,_mm256_set1_epi16(ch-64));
}

INLINE_AVX __m256i ascii_test(const unsigned char *p, unsigned ch) {
    __m256i raw=_mm256_i32gather_epi32((const int *)p,_mm256_setr_epi32(0,3,6,9,12,15,18,21),1);
    __m256i mask=_mm256_set1_epi32(255);
    __m256i a=_mm256_and_si256(raw,mask),b=_mm256_and_si256(_mm256_srli_epi32(raw,8),mask),c=_mm256_and_si256(_mm256_srli_epi32(raw,16),mask);
    __m256i code=_mm256_sub_epi32(_mm256_add_epi32(_mm256_add_epi32(_mm256_mullo_epi32(a,_mm256_set1_epi32(100)),_mm256_mullo_epi32(b,_mm256_set1_epi32(10))),c),_mm256_set1_epi32(5328));
    __m256i yes=_mm256_cmpeq_epi32(code,_mm256_set1_epi32(ch));
    if (ch==46) yes=_mm256_or_si256(yes,_mm256_or_si256(_mm256_cmpgt_epi32(_mm256_set1_epi32(32),code),_mm256_cmpgt_epi32(code,_mm256_set1_epi32(126))));
    return yes;
}

static uint64_t scalar_scan(const unsigned char *data,const unsigned char *q,uint64_t length,
                            int mode,uint64_t begin,uint64_t end,uint64_t *out,uint64_t cap) {
    uint64_t n=0;unsigned step=mode==3?3:mode?2:1;
    for(uint64_t i=begin;i<end;i++) {
        if (decode(data+i*step,mode)!=q[0]) continue;
        if (length>1 && decode(data+(i+length-1)*step,mode)!=q[length-1]) continue;
        if(equal_at(data,q,i,length,mode,step)) {out[n++]=i;if(n==cap) break;}
    }
    return n;
}

/* Three independent bytes reject 99.9% of decimal starts. Hoist broadcasts
 * and offsets, and test 64 starts per iteration to keep the hot loop small. */
AVX static uint64_t digit_scan(const unsigned char *data,const unsigned char *q,uint64_t length,
                               uint64_t begin,uint64_t end,uint64_t *out,uint64_t cap,unsigned stride) {
    if(length<3) {
        if(stride==1)return scalar_scan(data,q,length,0,begin,end,out,cap);
        uint64_t n=0;
        for(uint64_t at=begin;at<end;at++)if(!(at%stride) && !memcmp(data+at,q,(size_t)length)){out[n++]=at/stride;if(n==cap)break;}
        return n;
    }
    uint64_t mid=length/2,last=length-1,i=begin,n=0;
    uint64_t prefix=0;if(length>=8)memcpy(&prefix,q,8);
    __m256i a=_mm256_set1_epi8(q[0]),b=_mm256_set1_epi8(q[mid]),c=_mm256_set1_epi8(q[last]);
    for(;end-i>=64;i+=64) {
        __m256i x=_mm256_cmpeq_epi8(_mm256_loadu_si256((const __m256i *)(data+i)),a);
        __m256i y=_mm256_cmpeq_epi8(_mm256_loadu_si256((const __m256i *)(data+i+32)),a);
        x=_mm256_and_si256(x,_mm256_cmpeq_epi8(_mm256_loadu_si256((const __m256i *)(data+i+mid)),b));
        y=_mm256_and_si256(y,_mm256_cmpeq_epi8(_mm256_loadu_si256((const __m256i *)(data+i+mid+32)),b));
        x=_mm256_and_si256(x,_mm256_cmpeq_epi8(_mm256_loadu_si256((const __m256i *)(data+i+last)),c));
        y=_mm256_and_si256(y,_mm256_cmpeq_epi8(_mm256_loadu_si256((const __m256i *)(data+i+last+32)),c));
        uint64_t bits=(uint32_t)_mm256_movemask_epi8(x)|((uint64_t)(uint32_t)_mm256_movemask_epi8(y)<<32);
        while(bits){
            unsigned lane=__builtin_ctzll(bits);bits&=bits-1;uint64_t at=i+lane;
            if(stride>1 && at%stride)continue;
            if(length>=8){uint64_t head;memcpy(&head,data+at,8);if(head!=prefix)continue;}
            if(!memcmp(data+at,q,(size_t)length)){out[n++]=at/stride;if(n==cap)return n;}
        }
    }
    for(;i<end;i++)if((stride==1 || !(i%stride)) && !memcmp(data+i,q,(size_t)length)){out[n++]=i/stride;if(n==cap)break;}
    return n;
}

AVX static uint64_t vector_scan(const unsigned char *data,const unsigned char *q,uint64_t length,
                                int mode,uint64_t begin,uint64_t end,uint64_t *out,uint64_t cap) {
    uint64_t n=0,i=begin;unsigned step=mode==3?3:mode?2:1;
    unsigned lanes=mode==3?8:mode?16:32;
    uint64_t anchors[4]={0,length/3,(length*2)/3,length-1};
    unsigned used=length>=4?4:(unsigned)length;
    if(length<4)for(unsigned j=0;j<used;j++)anchors[j]=j;
    /* Two 26-letter filters already reject >99.8% of starts. Verifying the
     * survivors costs less than decoding two additional complete vectors. */
    if(mode==1 && length>1){used=2;anchors[0]=0;anchors[1]=length-1;}
    /* A gather reads four bytes per three-digit character: leave a unit of halo. */
    unsigned extra=mode==3?1:0;
    for(;end-i>=lanes+extra;i+=lanes) {
        __m256i yes=_mm256_set1_epi8(-1);
        for(unsigned j=0;j<used;j++) {
            const unsigned char *p=data+(i+anchors[j])*step;unsigned ch=q[anchors[j]];
            __m256i eq=!mode ? _mm256_cmpeq_epi8(_mm256_loadu_si256((const __m256i *)p),_mm256_set1_epi8(ch))
                            :mode==3 ? ascii_test(p,ch):pair_test(p,ch,mode);
            yes=_mm256_and_si256(yes,eq);
        }
        uint32_t bits=mode==3 ? (uint32_t)_mm256_movemask_ps(_mm256_castsi256_ps(yes)):(uint32_t)_mm256_movemask_epi8(yes);
        while(bits) {
            unsigned bit=__builtin_ctz(bits),lane=mode && mode!=3?bit/2:bit;
            if(mode && mode!=3)bits&=~(3u<<(lane*2));else bits&=bits-1;
            if(equal_at(data,q,i+lane,length,mode,step)) {out[n++]=i+lane;if(n==cap)return n;}
        }
    }
    return n+scalar_scan(data,q,length,mode,i,end,out+n,cap-n);
}

API int pi_scan_avx2(void) {
    unsigned a,b,c,d;
    if(!__get_cpuid(1,&a,&b,&c,&d) || (c&0x18000000u)!=0x18000000u)return 0;
    unsigned lo,hi;__asm__ volatile("xgetbv":"=a"(lo),"=d"(hi):"c"(0));
    if((lo&6)!=6)return 0;
    if(!__get_cpuid_count(7,0,&a,&b,&c,&d))return 0;
    return (b&32)?1:0;
}
API uint64_t pi_scan(const unsigned char *data,uint64_t units,const unsigned char *query,uint64_t length,
                     int mode,uint64_t begin,uint64_t end,uint64_t *out,uint64_t cap,int vector) {
    if (!length || !cap || length>units || mode<0 || mode>3)return 0;
    uint64_t stop=units-length+1;if(end>stop)end=stop;if(begin>=end)return 0;
    if (vector && pi_scan_avx2()) {
        if(!mode)return digit_scan(data,query,length,begin,end,out,cap,1);
        /* Printable ASCII and A1Z26 letters have unique decimal encodings.
         * Search those encoded bytes directly, keeping the requested alignment. */
        if((mode==2 || mode==3) && length<=2048 && !memchr(query,'.',(size_t)length)) {
            unsigned step=mode==3?3:2;unsigned char encoded[6144];
            for(uint64_t j=0;j<length;j++) {
                unsigned ch=mode==2?query[j]-64:query[j];
                if(step==3)encoded[j*step]=48+ch/100;
                encoded[j*step+step-2]=48+(ch/10)%10;encoded[j*step+step-1]=48+ch%10;
            }
            uint64_t rawend=end*step,rawstop=(units-length)*step+1;
            if(rawend>rawstop)rawend=rawstop;
            return digit_scan(data,encoded,length*step,begin*step,rawend,out,cap,step);
        }
        return vector_scan(data,query,length,mode,begin,end,out,cap);
    }
    return scalar_scan(data,query,length,mode,begin,end,out,cap);
}

/* Constraints are offsets in the raw digit grid; masks combine 32 candidate
 * starts at once. Rows may cross a worker boundary, but never the grid edge. */
AVX static uint64_t vector_shape(const unsigned char *data,uint64_t begin,uint64_t end,
        const uint64_t *offsets,const unsigned char *values,uint64_t constraints,
        uint64_t width,uint64_t shape_width,int parity,uint64_t *out,uint64_t cap) {
    uint64_t n=0,i=begin;
    for(;end-i>=32;i+=32) {
        __m256i yes=_mm256_set1_epi8(-1);
        uint64_t j=0;uint32_t bits=0xffffffffu;
        for(;j<constraints && j<16;j++) {
            __m256i raw=_mm256_loadu_si256((const __m256i *)(data+i+offsets[j]));
            __m256i on=parity?_mm256_cmpeq_epi8(_mm256_and_si256(raw,_mm256_set1_epi8(1)),_mm256_set1_epi8(1)):_mm256_cmpgt_epi8(raw,_mm256_set1_epi8('4'));
            yes=_mm256_and_si256(yes,values[j]?on:_mm256_xor_si256(on,_mm256_set1_epi8(-1)));
            bits=(uint32_t)_mm256_movemask_epi8(yes);if(!bits)break;
        }
        while(bits) {
            unsigned bit=__builtin_ctz(bits);bits&=bits-1;uint64_t at=i+bit;
            if(at%width+shape_width>width)continue;
            uint64_t k=j;for(;k<constraints;k++){unsigned d=data[at+offsets[k]];if((parity?(d&1):(d>='5'))!=values[k])break;}
            if(k==constraints){out[n++]=at;if(n==cap)return n;}
        }
    }
    for(;i<end;i++) {
        if(i%width+shape_width>width)continue;
        uint64_t j=0;for(;j<constraints;j++){unsigned d=data[i+offsets[j]];if((parity?(d&1):(d>='5'))!=values[j])break;}
        if(j==constraints){out[n++]=i;if(n==cap)return n;}
    }
    return n;
}

API uint64_t pi_shape(const unsigned char *data,uint64_t units,uint64_t begin,uint64_t end,
        const uint64_t *offsets,const unsigned char *values,uint64_t constraints,
        uint64_t extent,uint64_t width,uint64_t shape_width,int parity,uint64_t *out,uint64_t cap) {
    if(!constraints || !cap || !width || shape_width>width || extent>units)return 0;
    uint64_t stop=units-extent+1;if(end>stop)end=stop;if(begin>=end)return 0;
    if(pi_scan_avx2())return vector_shape(data,begin,end,offsets,values,constraints,width,shape_width,parity,out,cap);
    uint64_t n=0;
    for(uint64_t i=begin;i<end;i++) {
        if(i%width+shape_width>width)continue;
        uint64_t j=0;for(;j<constraints;j++){unsigned d=data[i+offsets[j]];if((parity?(d&1):(d>='5'))!=values[j])break;}
        if(j==constraints){out[n++]=i;if(n==cap)return n;}
    }
    return n;
}
