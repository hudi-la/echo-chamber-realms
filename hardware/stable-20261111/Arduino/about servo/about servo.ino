// #include <Servo.h>
// Servo myservo; 
#include <Servo.h> 
Servo myservo; 


// void setup() {
  // myservo.attach(2);
  // }

int servoPort = 7;

void setup(){
  myservo.attach(servoPort);
}



void loop() {
  // for (int pos = 0; pos <= 180; pos += 1) { // goes from 0 degrees to 180 degrees
  //   // in steps of 1 degree
  //   myservo.write(pos);              // tell servo to go to position in variable 'pos'
  //   delay(100);                       // waits 15ms for the servo to reach the position
  // }
  // for (int pos = 180; pos >= 0; pos -= 1) { // goes from 180 degrees to 0 degrees
  //   myservo.write(pos);              // tell servo to go to position in variable 'pos'
  //   delay(100);                       // waits 15ms for the servo to reach the position
  // }
  myservo.write(0); 
  delay(1000);
  myservo.write(180);
  delay(1000); 

  for(int pos=180; pos>=0; pos -= 20){
    myservo.write(pos); 
    delay(500);
  }
  // myservo.write(0);
  // delay(1000);
  // myservo.write(90);
  // delay(1000);
}
