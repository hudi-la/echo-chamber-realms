#include <Servo.h>

Servo motor;

void setup() {
  motor.attach(9);

  motor.writeMicroseconds(1500);  // 先回中
  delay(1500);

  motor.writeMicroseconds(1400);  // 向一侧小幅转动
  delay(1000);

  motor.writeMicroseconds(1600);  // 向另一侧小幅转动
  delay(1000);

  motor.writeMicroseconds(1500);  // 最后回中并保持
}

void loop() {
  // 不重复摆动
}
