#include <Servo.h> 
// Servo charlieservo; 
// Servo kaservo; 
// Servo lucyservo;

int incomingByte = 0;

int Charlie_port = 2;
int Kaka_port = 3;
int Lucy_port = 4;


void setup() {
  Serial.begin(9600);

  // charlieservo.attach(Charlie_port);
  // kaservo.attach(Kaka_port);
  // lucyservo.attach(Lucy_port);

  pinMode(Charlie_port, OUTPUT);   
  pinMode(Kaka_port, OUTPUT);   
  pinMode(Lucy_port, OUTPUT);   

  digitalWrite(Charlie_port, LOW); 
  digitalWrite(Kaka_port, LOW); 
  digitalWrite(Lucy_port, LOW); 
}

void loop() {
  // put your main code here, to run repeatedly:
  // send data only when you receive data:
  if (Serial.available() > 0) {
    // read the incoming byte:
    incomingByte = Serial.read();
    Serial.print("I received: ");
    Serial.println(incomingByte, DEC);

    if (incomingByte == 49) {
      digitalWrite(Charlie_port, HIGH); 
    }

    if (incomingByte == 50) {
      digitalWrite(Kaka_port, HIGH); 
    }

    if (incomingByte == 51) { 
      digitalWrite(Lucy_port, HIGH); 
    }

    if (incomingByte == 52) { 
      digitalWrite(Charlie_port, LOW); 
    }

    if (incomingByte == 53) { 
      digitalWrite(Kaka_port, LOW); 
    }

    if (incomingByte == 54) { 
      digitalWrite(Lucy_port, LOW); 
    }

    // say what you got:
    // Serial.print("I received: ");
    // Serial.println(incomingByte, DEC);
  }

  // charliemove();
  // kamove();

}

// void charliemove(){
//   charlieservo.write(0); 
//   delay(1000);
//   charlieservo.write(180);
//   delay(1000); 
// }

// void kamove(){
//   kaservo.write(0); 
//   delay(1000);
//   kaservo.write(180);
//   delay(1000); 
// }
