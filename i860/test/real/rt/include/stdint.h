#ifndef _STDINT_H
#define _STDINT_H
typedef signed char int8_t; typedef unsigned char uint8_t;
typedef short int16_t; typedef unsigned short uint16_t;
typedef int int32_t; typedef unsigned int uint32_t;
typedef long long int64_t; typedef unsigned long long uint64_t;
typedef int intptr_t; typedef unsigned int uintptr_t;
#define UINT32_MAX 0xffffffffU
#define INT32_MAX 0x7fffffff
#define UINT8_MAX 255
#define UINT16_MAX 65535
#endif
