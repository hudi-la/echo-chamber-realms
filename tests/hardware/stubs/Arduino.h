#pragma once
#include <stdint.h>
#define A0 14
#define A1 15
extern unsigned long fakeMillis;
inline unsigned long millis(){return fakeMillis;}
inline void delay(unsigned long ms){fakeMillis+=ms;}
template<class T> T constrain(T x,T a,T b){return x<a?a:(x>b?b:x);}
