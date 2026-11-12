#include <Servo.h>
Servo s_1; 
Servo s_2; 

int angle_1;
int angle_2;

const int servor_10 =  10; 
const int servor_11 =  11; 

void setup() {
  Serial.begin(9600); 

  s_1.attach(servor_10);
  s_2.attach(servor_11);

}

void loop() {
while(Serial.available()>0){//当有信号的时候
  angle_1 =Serial.read();
  s_1.write(angle_1);
  // delay(1000);
  // angle_2 =Serial.read();
  // s_2.write(angle_2);
  // delay(1000);
}

// int x = 0;
// while(x < 100){
//   s_1.write(1);
//   delay(1000);
//   s_1.write(0);
//   delay(1000);
// }

}