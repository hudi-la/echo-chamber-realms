#include <Servo.h>
Servo myservo; 

const int buttonApin = 2;
const int buttonBpin = 3;
const int buttonCpin = 4;

const int ledPin = 13;
const int ledAPin = 8;
const int ledBPin = 9;
const int ledCPin = 10;

void setup() 
{
  myservo.attach(12);
  
  pinMode(ledPin, OUTPUT);
  pinMode(ledAPin, OUTPUT);
  pinMode(ledBPin, OUTPUT);
  pinMode(ledCPin, OUTPUT);
  pinMode(buttonApin, INPUT_PULLUP);  // 按钮设置为input的状态
  pinMode(buttonBpin, INPUT_PULLUP);  // 按钮设置为input的状态
  pinMode(buttonCpin, INPUT_PULLUP);  // 按钮设置为input的状态

  Serial.begin(9600);

  digitalWrite(ledPin, HIGH);
  digitalWrite(ledAPin, HIGH);
  digitalWrite(ledBPin, HIGH);
  digitalWrite(ledCPin, HIGH);

  delay(687000  + 3000);

  // digitalWrite(ledAPin, HIGH);
  // digitalWrite(ledBPin, LOW);
  // digitalWrite(ledCPin, LOW);
  myservo.write(180);
  delay(138000 + 3000);

  // digitalWrite(ledAPin, LOW);
  // digitalWrite(ledBPin, HIGH);
  // digitalWrite(ledCPin, LOW);
  myservo.write(90);
  delay(134000  + 3000);

  // digitalWrite(ledAPin, LOW);
  // digitalWrite(ledBPin, LOW);
  // digitalWrite(ledCPin, HIGH);
  myservo.write(0);
  delay(151000  + 3000);

  // digitalWrite(ledAPin, HIGH);
  // digitalWrite(ledBPin, HIGH);
  // digitalWrite(ledCPin, HIGH);
  // myservo.write(180);
  myservo.write(90);
}

void loop() 
{
  if (digitalRead(buttonApin) == LOW) // 按钮在按下后是LOW的状态
  {
    digitalWrite(ledAPin, HIGH);
    digitalWrite(ledBPin, LOW);
    digitalWrite(ledCPin, LOW);

    myservo.write(180);

    Serial.println(1);
  }

  if (digitalRead(buttonBpin) == LOW) // 按钮在按下后是LOW的状态
  {
    digitalWrite(ledAPin, LOW);
    digitalWrite(ledBPin, HIGH);
    digitalWrite(ledCPin, LOW);

    myservo.write(90);

    Serial.println(2);
  }

  if (digitalRead(buttonCpin) == LOW) // 按钮在按下后是LOW的状态
  {
    digitalWrite(ledAPin, LOW);
    digitalWrite(ledBPin, LOW);
    digitalWrite(ledCPin, HIGH);

    myservo.write(0);

    Serial.println(3);
    // Serial.print(" ");
  }

}