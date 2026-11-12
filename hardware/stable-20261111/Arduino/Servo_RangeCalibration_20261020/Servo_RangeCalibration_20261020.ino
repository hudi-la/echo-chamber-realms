#include <Servo.h>

Servo motor;

// 只改这里选择要测试的引脚，例如 {8}、{9} 或 {8, 9, 10}。
// 请使用普通数字引脚，避开串口使用的 0、1。
const byte TEST_PINS[] = {9,10};
const byte TEST_COUNT = sizeof(TEST_PINS) / sizeof(TEST_PINS[0]);
byte activeIndex = 0;

// 这些普通数字引脚在不测试时保持 LOW，不发送舵机脉冲。
// 如果开发板还有其他连接舵机的数字引脚，也把它们加到这里。
const byte CONTROL_PINS[] = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13};

void disablePin(byte pin) {
  digitalWrite(pin, LOW);
  pinMode(pin, OUTPUT);
}

void disableMotor() {
  if (motor.attached()) {
    motor.detach();
  }
  disablePin(TEST_PINS[activeIndex]);
}

const int CENTER = 1500;

// 防止误输入，不代表机构在整个范围内都安全
const int MIN_PULSE = 500;
const int MAX_PULSE = 2500;

int position = CENTER;
int edgeA = -1;
int edgeB = -1;

void showPosition() {
  Serial.print("Current: ");
  Serial.print(position);
  Serial.println(" us");
}

// 切换前停止上一只舵机的信号，每只舵机单独记录范围。
void selectMotor(byte index) {
  disableMotor();
  activeIndex = index;
  position = CENTER;
  edgeA = -1;
  edgeB = -1;
  motor.writeMicroseconds(position);
  motor.attach(TEST_PINS[activeIndex]);
  Serial.print("Testing pin: ");
  Serial.println(TEST_PINS[activeIndex]);
  showPosition();
}

void setup() {
  for (byte i = 0; i < sizeof(CONTROL_PINS) / sizeof(CONTROL_PINS[0]); i++) {
    disablePin(CONTROL_PINS[i]);
  }
  for (byte i = 0; i < TEST_COUNT; i++) {
    disablePin(TEST_PINS[i]);
  }

  Serial.begin(115200);

  // 上电后按列表顺序各测试一次：回中、小幅摆动、回中。
  for (byte i = 0; i < TEST_COUNT; i++) {
    selectMotor(i);
    delay(1500);
    motor.writeMicroseconds(1400);
    delay(1000);
    motor.writeMicroseconds(1600);
    delay(1000);
    motor.writeMicroseconds(CENTER);
    delay(1000);
    disableMotor();
  }

  // 自动测试结束后全部停用；发送 n 才启用第一只，之后依次切换。
  activeIndex = TEST_COUNT - 1;
  Serial.println("Auto test done. All servo signals disabled.");
  Serial.println("n: next pin | x: disable all servo signals");
  Serial.println("+/-: 5 us | u/d: 10 us | U/D: 50 us");
  Serial.println("c: center | a/b: save | p: show saved");
}

void loop() {
  if (!Serial.available()) return;

  String command = Serial.readStringUntil('\n');
  command.trim();
  if (command.length() == 0) return;

  // 每条消息只接受一个字符，避免一次误发很多步
  if (command.length() != 1) {
    Serial.println("Send ONE character only.");
    return;
  }

  char key = command.charAt(0);
  if (key == 'n') {
    selectMotor((activeIndex + 1) % TEST_COUNT);
    return;
  }
  if (key == 'x') {
    disableMotor();
    Serial.println("All servo signals disabled.");
    return;
  }
  if (!motor.attached()) {
    Serial.println("Send n to enable the next test pin first.");
    return;
  }
  int change = 0;

  switch (key) {
    case '+': change = 5;   break;
    case '-': change = -5;  break;
    case 'u': change = 10;  break;
    case 'd': change = -10; break;
    case 'U': change = 50;  break;
    case 'D': change = -50; break;

    case 'c':
      position = CENTER;
      motor.writeMicroseconds(position);
      showPosition();
      return;

    case 'a':
      edgeA = position;
      Serial.print("Saved A: ");
      Serial.println(edgeA);
      return;

    case 'b':
      edgeB = position;
      Serial.print("Saved B: ");
      Serial.println(edgeB);
      return;

    case 'p':
      Serial.print("Center: 1500 | A: ");
      Serial.print(edgeA);
      Serial.print(" | B: ");
      Serial.println(edgeB);
      Serial.println("Units: us; -1 = not recorded");
      return;

    default:
      Serial.println("Unknown command.");
      return;
  }

  int next = position + change;

  if (next < MIN_PULSE || next > MAX_PULSE) {
    Serial.println("Software limit reached.");
    return;
  }

  position = next;
  motor.writeMicroseconds(position);
  showPosition();
}
