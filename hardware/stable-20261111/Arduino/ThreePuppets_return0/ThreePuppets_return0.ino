#include <Servo.h>

// 当前接线：鸟眼皮 A0/A1、眼球 D2/D3；狗 D4-D7；老鼠 D8-D10。
// D0/D1 留给串口。115200 波特率，发送 T 或 t 再运行一轮。
// 上电/复位自动执行一次，结束后全部保持回正。
const byte SERVO_COUNT = 11;
Servo servos[SERVO_COUNT];

// 顺序：鸟左眼皮、鸟右眼皮、鸟上下、鸟左右、
//       狗左眼皮、狗右眼皮、狗上下、狗左右、
//       老鼠左右、老鼠眼皮、老鼠抬头低头。
const byte SERVO_PINS[SERVO_COUNT] = {A0, A1, 2, 3, 4, 5, 6, 7, 8, 9, 10};

// 回正使用安装中位。老鼠尚无实测中位记录，暂用 1500；可逐项修改。
const int CENTER_US[SERVO_COUNT] = {
  1500, 1500, 1500, 1500,
  1500, 1500, 1500, 1500,
  1500, 1500, 1500
};

// 每次只测试一个舵机，其他舵机保持中位。
// 顺序：鸟左右、上下、左眼皮、右眼皮；
//       老鼠左右、眼皮、抬头低头；狗左右、上下、左眼皮、右眼皮。
const byte TEST_ORDER[SERVO_COUNT] = {3, 2, 0, 1, 8, 9, 10, 7, 6, 4, 5};
const char* const TEST_NAMES[SERVO_COUNT] = {
  "Bird yaw", "Bird pitch", "Bird left lid", "Bird right lid",
  "Mouse yaw", "Mouse lid", "Mouse head",
  "Dog yaw", "Dog pitch", "Dog left lid", "Dog right lid"
};
// 第一侧的方向；鸟/狗沿用已记录的左、上、闭眼方向。
// 老鼠方向未校准，先做正负小幅测试，不代表已确认实际方向。
const int FIRST_SIGN[SERVO_COUNT] = {1, 1, 1, -1, 1, 1, 1, -1, 1, 1, -1};
const int SWING_US = 50;            // 所有舵机相对中位各动 +/-50 微秒
const unsigned long HOLD_MS = 600;  // 到位后停留
int currentUs[SERVO_COUNT];

// 直接发送目标位置，不插值、不做缓动。
void moveDirectly(byte index, int targetUs) {
  currentUs[index] = targetUs;
  servos[index].writeMicroseconds(targetUs);
  delay(HOLD_MS);
}

void setup() {
  Serial.begin(115200);
  // 未使用的信号端保持低电平；直流电机不执行任何动作。
  for (byte pin = 11; pin <= 13; pin++) {
    digitalWrite(pin, LOW);
    pinMode(pin, OUTPUT);
  }

  // 先预设回正脉宽，再启用所有舵机。
  // 上电时实际位置未知，首次回正速度由舵机自身决定。
  for (byte i = 0; i < SERVO_COUNT; i++) {
    currentUs[i] = CENTER_US[i];
    servos[i].writeMicroseconds(currentUs[i]);
    servos[i].attach(SERVO_PINS[i]);
  }
  delay(2500);

  runRound();
}

void runRound() {
  Serial.println("START: bird -> mouse -> dog");
  for (byte step = 0; step < SERVO_COUNT; step++) {
    byte index = TEST_ORDER[step];
    int center = CENTER_US[index];
    Serial.println(TEST_NAMES[step]);
    moveDirectly(index, center + FIRST_SIGN[step] * SWING_US);
    moveDirectly(index, center - FIRST_SIGN[step] * SWING_US);
    moveDirectly(index, center);
    // 每个角色测试完成后稍作停留。
    if (step == 3 || step == 6 || step == 10) delay(1000);
  }
  // 丢弃动作期间收到的输入，防止积压 T 后连续重跑。
  while (Serial.available() > 0) Serial.read();
  Serial.println("DONE. Send T to run again.");
}

void loop() {
  if (Serial.available() > 0) {
    char key = Serial.read();
    if (key == 'T' || key == 't') runRound();
  }
  // Servo 库持续输出信号，保持回正姿态。
}
