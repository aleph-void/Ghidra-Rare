#ifndef _CTYPE_H
#define _CTYPE_H
static inline int isdigit(int c){return c>=48&&c<=57;}
static inline int isspace(int c){return c==32||(c>=9&&c<=13);}
static inline int isalpha(int c){return (c|32)>=97&&(c|32)<=122;}
static inline int isalnum(int c){return isalpha(c)||isdigit(c);}
static inline int isxdigit(int c){return isdigit(c)||((c|32)>=97&&(c|32)<=102);}
static inline int isupper(int c){return c>=65&&c<=90;}
static inline int islower(int c){return c>=97&&c<=122;}
static inline int tolower(int c){return isupper(c)?c+32:c;}
static inline int toupper(int c){return islower(c)?c-32:c;}
#endif
