#define lengh 64

const int mic1  = A0;
const int mic2  = A1;
const int mic3  = A2;
const int mic4  = A3;

int data_1[lengh];
int data_2[lengh];
int data_3[lengh];
int data_4[lengh];

// #include <Servo.h>
// Servo myservo; 
// int servor =  11; 
// int servoAngle;
// int servoAngle_init = 90;

void setup() {
  // myservo.attach(servor);
  
  Serial.begin(9600);
  

}

void loop() {
for(int i = 0; i < lengh; i++ ){
    data_1[i] = analogRead(mic1);
    data_2[i] = analogRead(mic2);
    data_3[i] = analogRead(mic3);
    data_4[i] = analogRead(mic4);

    Serial.print(data_1[i]);
    Serial.print(" ");
    Serial.print(data_2[i]);
    Serial.print(" ");
    Serial.print(data_3[i]);
    Serial.print(" ");
    Serial.println(data_4[i]);
  }  
  // myservo.write(random(180));
  // delay(100);
}


