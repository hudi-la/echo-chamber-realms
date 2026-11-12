#include <Servo.h>

// 三角色联合自然动作：鸟 -> 老鼠 -> 狗。
// 眨眼，睁眼同时看记录中的最左、最上；老鼠只向左，不用抬头轴代替眼球上下。
// 不做插值或缓动。上电执行一轮，串口 115200，T/t 再执行一轮。
// 接线：鸟 A0/A1/D2/D3；狗 D4/D5/D6/D7；老鼠 D8/D9/D10。
// D0/D1 仅用于串口；直流电机控制端 D12/D13 保持 LOW。
const byte COUNT = 11;
const byte PINS[COUNT] = {A0, A1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
Servo servo[COUNT];

// 数组下标：鸟左眼皮0、右眼皮1、上下2、左右3；
// 狗左眼皮4、右眼皮5、上下6、左右7；老鼠左右8、眼皮9、抬头10。
const int BIRD_REST_L = 1425;
const int BIRD_REST_R = 1600;
const int BIRD_OPEN_L = 725;
const int BIRD_OPEN_R = 2350;
const int BIRD_CLOSED_L = 2050;
const int BIRD_CLOSED_R = 950;
const int DOG_OPEN_L = 850;
const int DOG_OPEN_R = 2200;
const int DOG_CLOSED_L = 2200;
const int DOG_CLOSED_R = 850;
// 来源：老鼠_行程测量记录.txt（2026-10-20）。
// 2026-10-20 用户现场确认：所有视线左右均以木偶本人视角命名。
const int MOUSE_OPEN = 1450;
const int MOUSE_CLOSED = 2000;
const int MOUSE_LEFT = 1300; // 木偶自己的左 = 观众面对它时的右；另一侧1650。
// 以下左右均按木偶本人视角。鸟保持原动作；狗、老鼠按现场观察反转旧命名。
// 单轴端点不是组合无碰撞的保证，眼球上看时眼皮使用已记录的全开位置。
const int BIRD_LEFT = 2050; // 鸟：另一侧为 1050。
const int BIRD_UP = 2150; // 鸟：下方为 1105。
const int DOG_LEFT = 2000; // 木偶自己的左；右为900。
const int DOG_UP = 1900; // 狗：下方为 1100。
const unsigned long BLINK_MS = 220;
const unsigned long LOOK_MS = 1800; // 到位后停留，非缓动时间
const unsigned long BETWEEN_MS = 700;

void restBird() {
  servo[2].writeMicroseconds(1500);
  servo[3].writeMicroseconds(1500);
  servo[0].writeMicroseconds(BIRD_REST_L);
  servo[1].writeMicroseconds(BIRD_REST_R);
}

void restMouse() {
  servo[8].writeMicroseconds(1500);
  servo[9].writeMicroseconds(MOUSE_OPEN);
  servo[10].writeMicroseconds(1500);
}

void restDog() {
  servo[6].writeMicroseconds(1500);
  servo[7].writeMicroseconds(1500);
  servo[4].writeMicroseconds(1500);
  servo[5].writeMicroseconds(1500);
}

void runRound() {
  restBird();
  restMouse();
  restDog();
  delay(BETWEEN_MS);

  Serial.println("Bird: blink, open + look upper-left");
  servo[0].writeMicroseconds(BIRD_CLOSED_L);
  servo[1].writeMicroseconds(BIRD_CLOSED_R);
  delay(BLINK_MS);
  // 一组目标连续发送，中间不等待：睁眼与转动视线一起发起。
  servo[0].writeMicroseconds(BIRD_OPEN_L);
  servo[1].writeMicroseconds(BIRD_OPEN_R);
  servo[3].writeMicroseconds(BIRD_LEFT);
  servo[2].writeMicroseconds(BIRD_UP);
  delay(LOOK_MS);
  restBird();
  delay(BETWEEN_MS);

  Serial.println("Mouse: blink, open + look left");
  servo[9].writeMicroseconds(MOUSE_CLOSED);
  delay(BLINK_MS);
  servo[9].writeMicroseconds(MOUSE_OPEN);
  servo[8].writeMicroseconds(MOUSE_LEFT);
  delay(LOOK_MS);
  restMouse();
  delay(BETWEEN_MS);

  Serial.println("Dog: blink, open + look upper-left");
  servo[4].writeMicroseconds(DOG_CLOSED_L);
  servo[5].writeMicroseconds(DOG_CLOSED_R);
  delay(BLINK_MS);
  servo[4].writeMicroseconds(DOG_OPEN_L);
  servo[5].writeMicroseconds(DOG_OPEN_R);
  servo[7].writeMicroseconds(DOG_LEFT);
  servo[6].writeMicroseconds(DOG_UP);
  delay(LOOK_MS);
  restDog();
  delay(BETWEEN_MS);

  // 忽略动作期间收到的重复指令，避免排队连跑。
  while (Serial.available() > 0) Serial.read();
  Serial.println("DONE. Send T to repeat.");
}

void setup() {
  Serial.begin(115200);
  for (byte pin = 11; pin <= 13; pin++) {
    digitalWrite(pin, LOW);
    pinMode(pin, OUTPUT);
  }
  const int initial[COUNT] = {
    BIRD_REST_L, BIRD_REST_R, 1500, 1500,
    1500, 1500, 1500, 1500,
    1500, MOUSE_OPEN, 1500
  };
  for (byte i = 0; i < COUNT; i++) {
    servo[i].writeMicroseconds(initial[i]);
    servo[i].attach(PINS[i]);
  }
  delay(2500);
  runRound();
}

void loop() {
  if (Serial.available() > 0) {
    char key = Serial.read();
    if (key == 'T' || key == 't') runRound();
  }
}
