#define lengh 64

const int mic1  = A0;
const int mic2  = A1;

int data_1[lengh];
int data_2[lengh];

#include <Servo.h>
Servo myservo; 
int servor =  11; 
int servoAngle;
int servoAngle_init = 90;

void setup() {
  myservo.attach(servor);
  
  Serial.begin(9600);
}

void loop() {
  // int val_1 = analogRead(mic1);
  // int val_2 = analogRead(mic2);
  // Serial.println(val_1-1000);
  // Serial.println(val_2+1000);


  for(int i = 0; i < lengh; i++ ){
    data_1[i] = analogRead(mic1);
    data_2[i]= analogRead(mic2);

    Serial.print(data_1[i]-1000 );
    Serial.print(" ");
    Serial.println(data_2[i]);
  }  


  // servoAngle = Serial.read();
  // myservo.write(servoAngle);


  myservo.write(random(180));
  delay(100);

}
