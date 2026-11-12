
// const int greenledPin =  13;   
const int redledPin =  13;     // the number of the LED pin


void setup() {
  // initialize the LED pin as an output:
  pinMode(redledPin, OUTPUT);
  // pinMode(greenledPin, OUTPUT);

}

void loop() {

  int x = 0;
do {
  // digitalWrite(greenledPin, HIGH);
  // digitalWrite(redledPin, LOW);
  // delay(1000);
  // digitalWrite(greenledPin, LOW);
  digitalWrite(redledPin, HIGH);
  // delay(1000);
} while (x < 100);
  

}

