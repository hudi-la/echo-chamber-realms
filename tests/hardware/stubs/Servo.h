#pragma once
extern int pulse[20];
class Servo {
 int pin=-1, value=1500;
 public:
 void attach(int p){pin=p;pulse[pin]=value;}
 void writeMicroseconds(int v){value=v;if(pin>=0)pulse[pin]=v;}
};
