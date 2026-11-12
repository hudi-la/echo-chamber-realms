
int red = 7, green = 8;  

void setup() {
  // initialize the LED pin as an output:
  pinMode(red, OUTPUT);
  pinMode(green, OUTPUT);
//  pinMode(redledPin, OUTPUT);
//  pinMode(greenledPin, OUTPUT);

}

void loop() {
  digitalWrite(red, HIGH);
  digitalWrite(green, HIGH);
  delay(1000);
  digitalWrite(red, LOW);
  digitalWrite(green, LOW);
  delay(1000);
  //digitalWrite(greenledPin, HIGH);
//  digitalWrite(redledPin, LOW);
//  delay(1000);
//  digitalWrite(greenledPin, LOW);
//  digitalWrite(redledPin, HIGH);
//  delay(1000);

}

