#include <Servo.h>
#include <math.h>

Servo m[4];

// 安装中位仍为 1500；日常放松位置单独设置。
const int REST_L = 1425;
const int OPEN_L = 725; // 左眼向闭眼方向微调 25 us，闭眼端点仍为 2050。
const int REST_R = 1600;

// 左右、上下、左上眼睑、右上眼睑
const byte pin[4] = {9, 10, 5, 6};

const int view[8][2] = {
  {2050, 1500},  // 左
  {1050, 1500},  // 右
  {1500, 2150},  // 上
  {1500, 1105},  // 下
  {2050, 2150},  // 左上
  {1050, 2150},  // 右上
  {2050, 1105},  // 左下
  {1050, 1105}   // 右下
};

const char* label[8] = {
  "LEFT", "RIGHT", "UP", "DOWN",
  "LEFT-UP", "RIGHT-UP", "LEFT-DOWN", "RIGHT-DOWN"
};

int p[4] = {1500, 1500, 1500, 1500};
int from[4];

bool active = false;
bool attachedEyes = false;
bool blinkNow = false;

byte state = 0;
byte indexNow = 0;
byte roundNo = 0;

unsigned long began = 0;
unsigned long span = 1;
unsigned long tick = 0;

char key = 0;
byte chars = 0;

float ease(float t) {
  return t * t * (3 - 2 * t);
}

float mix(float a, float b, float t) {
  return a + (b - a) * t;
}

void enter(byte next, unsigned long ms) {
  state = next;
  span = ms;
  began = millis();

  for (byte i = 0; i < 4; i++) {
    from[i] = p[i];
  }
}

void writePose() {
  const int low[4]  = {1050, 1105, 700, 950};
  const int high[4] = {2050, 2150, 2050, 2350};

  for (byte i = 0; i < 4; i++) {
    p[i] = constrain(p[i], low[i], high[i]);

    if (i >= 2 || attachedEyes) {
      m[i].writeMicroseconds(p[i]);
    }
  }
}

// 仰视时的眼睑抬升曲线。
// 这是待实物验证的曲线，不是碰撞检测。
float lift(float pitch) {
  float amount = (pitch - 1500) / 650.0f;
  amount = constrain(amount, 0.0f, 1.0f);
  return sqrtf(amount);
}

void nextLook() {
  // 有些动作眨眼，有些不眨；每轮稍有变化
  blinkNow = ((indexNow + roundNo) % 3 != 0);

  Serial.print(label[indexNow]);
  Serial.println(blinkNow ? " + BLINK" : " DIRECT");

  enter(blinkNow ? 3 : 4, blinkNow ? 280 : 1200);
}

void command(char c) {
  if (c == 'h') {
    active = false;
    Serial.println("HOLD: torque remains ON.");

  } else if (c == 'x') {
    active = false;
    attachedEyes = false;

    for (byte i = 0; i < 4; i++) {
      m[i].detach();
    }

    Serial.println("Signals OFF, not power OFF.");

  } else if (c == 'g') {
    if (active) return;

    // 启动位置未知：先打开眼睑，再让眼球回正
    m[0].detach();
    m[1].detach();
    attachedEyes = false;

    p[2] = OPEN_L;
    p[3] = 2350;

    for (byte i = 2; i < 4; i++) {
      m[i].writeMicroseconds(p[i]);
      m[i].attach(pin[i]);
    }

    indexNow = 0;
    roundNo++;
    active = true;
    enter(0, 2000);

    Serial.println("START: open lids, then align.");
    Serial.println("One round only.");

  } else if (c == 'p') {
    Serial.print("yaw pitch lidL lidR: ");

    for (byte i = 0; i < 4; i++) {
      Serial.print(p[i]);
      Serial.print(' ');
    }

    Serial.println();
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("Automatic startup alignment...");

  // 先打开眼睑，避免眼球原本朝上时发生碰撞
  p[2] = OPEN_L;
  p[3] = 2350;

  for (byte i = 2; i < 4; i++) {
    m[i].writeMicroseconds(p[i]);
    m[i].attach(pin[i]);
  }
  delay(2000);

  // 再让眼球回到平视正前方
  for (byte i = 0; i < 2; i++) {
    p[i] = 1500;
    m[i].writeMicroseconds(1500);
    m[i].attach(pin[i]);
  }
  attachedEyes = true;
  delay(1500);

  // 平视后，上眼睑缓慢回到安装中位
  for (int step = 0; step <= 100; step++) {
    p[2] = OPEN_L + (1500L - OPEN_L) * step / 100;
    p[3] = 2350 - 850L * step / 100;
    writePose();
    delay(15);
  }

  // 左右小幅摆动，最后回正
  for (int pulse = 1500; pulse <= 1600; pulse += 5) {
    p[0] = pulse;
    writePose();
    delay(25);
  }
  delay(250);

  for (int pulse = 1600; pulse >= 1400; pulse -= 5) {
    p[0] = pulse;
    writePose();
    delay(25);
  }
  delay(250);

  for (int pulse = 1400; pulse <= 1500; pulse += 5) {
    p[0] = pulse;
    writePose();
    delay(25);
  }

  // 全部保持安装中位
  for (byte i = 0; i < 4; i++) {
    p[i] = 1500;
    from[i] = 1500;
  }
  writePose();

  // 完成安装中位回正和摆动后，进入日常放松姿态。
  for (int step = 0; step <= 100; step++) {
    p[2] = 1500 + (REST_L - 1500) * (long)step / 100;
    p[3] = 1500 + (REST_R - 1500) * (long)step / 100;
    writePose();
    delay(5);
  }
  for (byte i = 0; i < 4; i++) from[i] = p[i];

  active = false;
  state = 0;
  indexNow = 0;
  tick = millis();

  Serial.println("READY: gaze 1500; relaxed lids L=1425 R=1600.");
  Serial.println("g: demo; h: hold; x: signals off; p: position");
}

void loop() {
  // 一次只接受一行一个字符
  for (byte n = 0; n < 24 && Serial.available(); n++) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      if (chars == 1) {
        command(key);
      } else if (chars > 1) {
        Serial.println("One character per line.");
      }

      chars = 0;

    } else {
      key = c;
      if (chars < 2) chars++;
    }
  }

  if (!active) return;

  unsigned long now = millis();

  if ((unsigned long)(now - tick) < 20) return;
  tick = now;

  unsigned long elapsed = now - began;
  float t = elapsed >= span ? 1.0f : (float)elapsed / span;
  float f = ease(t);

  if (state == 2) {
    // 启动回正后，眼睑回到日常放松位置
    p[2] = mix(from[2], REST_L, f);
    p[3] = mix(from[3], REST_R, f);

  } else if (state == 3) {
    // 只在眼球平视时闭眼
    p[2] = mix(from[2], 2050, f);
    p[3] = mix(from[3], 950, f);

  } else if (state == 4) {
    // 眨眼时：睁开一部分后，转眼与继续睁眼重叠进行
    float travel;

    if (blinkNow) {
      float progress = (t - 0.45f) / 0.55f;
      progress = constrain(progress, 0.0f, 1.0f);
      travel = ease(progress);
    } else {
      travel = f;
    }

    p[0] = mix(1500, view[indexNow][0], travel);
    p[1] = mix(1500, view[indexNow][1], travel);

    float up = lift(p[1]);

    if (blinkNow) {
      float leftOpen = f;
      float rightOpen = f;

      if (travel > 0) {
        leftOpen = fmaxf(
          leftOpen,
          (2050 - REST_L + (REST_L - OPEN_L) * up) / (2050.0f - OPEN_L)
        );

        rightOpen = fmaxf(
          rightOpen,
          (REST_R - 950 + (2350 - REST_R) * up) / 1400.0f
        );
      }

      p[2] = 2050 - (2050 - OPEN_L) * leftOpen;
      p[3] = 950 + 1400 * rightOpen;

    } else {
      p[2] = REST_L - (REST_L - OPEN_L) * up;
      p[3] = REST_R + (2350 - REST_R) * up;
    }

  } else if (state == 6) {
    // 眼球与眼睑一起回正，仰视过程中继续保留抬升
    p[0] = mix(from[0], 1500, f);
    p[1] = mix(from[1], 1500, f);

    float up = lift(p[1]);

    p[2] = fminf(
      mix(from[2], REST_L, f),
      REST_L - (REST_L - OPEN_L) * up
    );

    p[3] = fmaxf(
      mix(from[3], REST_R, f),
      REST_R + (2350 - REST_R) * up
    );
  }

  writePose();

  if (elapsed < span) return;

  switch (state) {
    case 0:
      // 眼睑已等待打开，再启用眼球回正
      for (byte i = 0; i < 2; i++) {
        p[i] = 1500;
        m[i].writeMicroseconds(1500);
        m[i].attach(pin[i]);
      }

      attachedEyes = true;
      enter(1, 1500);
      break;

    case 1:
      enter(2, 1000);
      break;

    case 2:
      nextLook();
      break;

    case 3:
      enter(4, 1600);
      break;

    case 4:
      // 目标停留时间略有不同
      enter(5, 700 + (indexNow % 3) * 200);
      break;

    case 5:
      enter(6, 1400);
      break;

    case 6:
      enter(7, 400);
      break;

    case 7:
      indexNow++;

      if (indexNow == 8) {
        active = false;
        Serial.println("DONE. Holding relaxed pose; g repeats.");
      } else {
        nextLook();
      }
      break;
  }
}
