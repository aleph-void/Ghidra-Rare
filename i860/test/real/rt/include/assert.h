#ifndef _ASSERT_H
#define _ASSERT_H
#include <stdlib.h>
#define assert(x) ((x) ? (void)0 : abort())
#endif
