#include <Servo.h>
#include <math.h>

Servo servo[4];

// 左右、上下、左上眼睑、右上眼睑
const byte PINS[4] = {9, 10, 5, 6};

const int MIN_US[4] = {1050, 1105, 700, 950};
const int MAX_US[4] = {2050, 2150, 2050, 2350};

// 使用完整实测端点
const int GAZE[8][2] = {
  {2050, 1500},
  {1050, 1500},
  {1500, 2150},
  {1500, 1105},  // 下
  {2050, 2150},
  {1050, 2150},
  {2050, 1105},  // 左下
  {1050, 1105}   // 右下
};

const char *NAMES[8] = {
  "LEFT", "RIGHT", "UP", "DOWN",
  "LEFT-UP", "RIGHT-UP", "LEFT-DOWN", "RIGHT-DOWN"
};

const unsigned long MOVE_MS = 5000;

int currentUs[4] = {1500, 1500, 1500, 1500};
int startYaw = 1500;
int startPitch = 1500;
int targetYaw = 1500;
int targetPitch = 1500;

bool enabled = false;
bool moving = false;
bool paused = false;

int stepIndex = -1;
unsigned long moveStarted = 0;
unsigned long lastUpdate = 0;

char inputChar = 0;
byte inputCount = 0;

void showPosition() {
  Serial.print("yaw pitch lidL lidR: ");

  for (byte i = 0; i < 4; i++) {
    Serial.print(currentUs[i]);
    Serial.print(' ');
  }

  Serial.println("us");
}

// 根据眼球当前俯仰指令计算眼睑位置。
// 平视/向下：眼睑保持安装中位。
// 向上：眼睑连续抬起，前段抬得较快。
// 这是待实物验证的跟随曲线，不是碰撞保证。
void updateLids(float pitchUs) {
  float up = (pitchUs - 1500.0f) / 650.0f;

  if (up < 0.0f) up = 0.0f;
  if (up > 1.0f) up = 1.0f;

  float lift = sqrtf(up);

  currentUs[2] = (int)(1500.0f - 800.0f * lift);
  currentUs[3] = (int)(1500.0f + 850.0f * lift);
}

void writePose() {
  for (byte i = 0; i < 4; i++) {
    int pulse = currentUs[i];

    if (pulse < MIN_US[i]) pulse = MIN_US[i];
    if (pulse > MAX_US[i]) pulse = MAX_US[i];

    currentUs[i] = pulse;
    servo[i].writeMicroseconds(pulse);
  }
}

void updateMovement() {
  if (!moving) return;

  unsigned long elapsed = millis() - moveStarted;

  float t = elapsed >= MOVE_MS
    ? 1.0f
    : (float)elapsed / MOVE_MS;

  // 平滑起步、平滑停下
  float blend = t * t * (3.0f - 2.0f * t);

  float yaw = startYaw
    + (targetYaw - startYaw) * blend;

  float pitch = startPitch
    + (targetPitch - startPitch) * blend;

  currentUs[0] = (int)yaw;
  currentUs[1] = (int)pitch;

  // 同一次更新里计算眼球和眼睑
  updateLids(pitch);
  writePose();

  if (elapsed >= MOVE_MS) {
    moving = false;
    Serial.println("ARRIVED. Inspect before sending n.");
    showPosition();
  }
}

void nextStep() {
  if (!enabled) {
    Serial.println("Send e first.");
    return;
  }

  if (paused) {
    Serial.println("PAUSED. Inspect and restore neutral before restarting.");
    return;
  }

  if (moving) {
    Serial.println("BUSY. No command queued.");
    return;
  }

  if (stepIndex >= 15) {
    Serial.println("DONE: eight directions checked.");
    return;
  }

  stepIndex++;

  byte direction = stepIndex / 2;
  bool returning = (stepIndex % 2) == 1;

  startYaw = currentUs[0];
  startPitch = currentUs[1];

  if (returning) {
    targetYaw = 1500;
    targetPitch = 1500;
    Serial.println("RETURN CENTER");
  } else {
    targetYaw = GAZE[direction][0];
    targetPitch = GAZE[direction][1];
    Serial.println(NAMES[direction]);
  }

  Serial.print("STEP ");
  Serial.print(stepIndex + 1);
  Serial.println("/16");

  moveStarted = millis();
  moving = true;
}

void handleCommand(char c) {
  if (c == 'e') {
    if (enabled) {
      Serial.println("Already enabled.");
      return;
    }

    // 仅在实物已经处于安装中位时启用。
    // 不知道断电后的真实位置，不能保证首次回中路径。
    for (byte i = 0; i < 4; i++) {
      currentUs[i] = 1500;
      servo[i].writeMicroseconds(1500);
      servo[i].attach(PINS[i]);
    }

    enabled = true;
    moving = false;
    paused = false;
    stepIndex = -1;

    Serial.println("Enabled at 1500. Send n for LEFT.");
    showPosition();

  } else if (c == 'n') {
    nextStep();

  } else if (c == 'h') {
    // 保持最后发送的位置，不再前进一步
    moving = false;
    paused = true;

    Serial.println("HOLD. Torque remains ON.");
    showPosition();

  } else if (c == 'x') {
    moving = false;
    enabled = false;
    paused = false;

    for (byte i = 0; i < 4; i++) {
      servo[i].detach();
    }

    Serial.println("Signals OFF. Electrical power is NOT cut.");

  } else if (c == 'p') {
    showPosition();

  } else {
    Serial.println("e enable; n next; h hold; x off; p position");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("Starting alignment...");

  // 1. 先打开上眼睑，给眼球让出空间
  servo[2].writeMicroseconds(700);
  servo[3].writeMicroseconds(2350);
  servo[2].attach(PINS[2]);
  servo[3].attach(PINS[3]);
  delay(1800);

  // 2. 眼睑打开后，眼球上下、左右回正
  servo[0].writeMicroseconds(1500);
  servo[1].writeMicroseconds(1500);
  servo[0].attach(PINS[0]);
  servo[1].attach(PINS[1]);
  delay(1500);

  // 3. 平视后，两片上眼睑缓慢回到安装中位
  for (int step = 0; step <= 100; step++) {
    int leftLid  = 700  + 800L * step / 100;
    int rightLid = 2350 - 850L * step / 100;

    servo[2].writeMicroseconds(leftLid);
    servo[3].writeMicroseconds(rightLid);
    delay(15);
  }

  // 4. 左右小幅摆动：1500 → 1600 → 1400 → 1500
  // 上下轴保持平视，眼睑保持中位
  for (int pulse = 1500; pulse <= 1600; pulse += 5) {
    servo[0].writeMicroseconds(pulse);
    delay(25);
  }
  delay(300);

  for (int pulse = 1600; pulse >= 1400; pulse -= 5) {
    servo[0].writeMicroseconds(pulse);
    delay(25);
  }
  delay(300);

  for (int pulse = 1400; pulse <= 1500; pulse += 5) {
    servo[0].writeMicroseconds(pulse);
    delay(25);
  }

  // 5. 更新程序状态，最后全部保持1500
  for (byte i = 0; i < 4; i++) {
    currentUs[i] = 1500;
  }

  startYaw = targetYaw = 1500;
  startPitch = targetPitch = 1500;

  enabled = true;
  moving = false;
  paused = false;
  stepIndex = -1;
  lastUpdate = millis();

  Serial.println("READY: centered. Send n to start gaze test.");
  showPosition();
}

void loop() {
  for (byte n = 0; n < 24 && Serial.available(); n++) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      if (inputCount == 1) {
        handleCommand(inputChar);
      } else if (inputCount > 1) {
        Serial.println("Send ONE character per line.");
      }

      inputCount = 0;

    } else {
      inputChar = c;
      if (inputCount < 2) inputCount++;
    }
  }

  if (!enabled || !moving) return;

  unsigned long now = millis();

  if ((unsigned long)(now - lastUpdate) >= 20) {
    lastUpdate = now;
    updateMovement();
  }
}
