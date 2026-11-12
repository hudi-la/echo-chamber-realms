#include <Servo.h>

Servo s[4];
const byte pins[4] = {9, 10, 5, 6};
const int lo[4] = {1050, 1100, 700, 950};
const int hi[4] = {2050, 2150, 2050, 2350};
const int gaze[4][2] = {
  {1275, 1825}, {1775, 1825},
  {1275, 1300}, {1775, 1300}
};

int pos[4] = {1500, 1500, 1500, 1500};
int src[4], dst[4], back[4];
bool armed = false, moving = false, paused = false;
int stepNo = -1;
unsigned long began = 0, tick = 0;
char input = 0;
byte count = 0;

void show() {
  Serial.print("yaw pitch lidL lidR: ");
  for (byte i = 0; i < 4; i++) {
    Serial.print(pos[i]);
    Serial.print(' ');
  }
  Serial.println("us");
}

void updateMotion() {
  if (!moving) return;

  unsigned long elapsed = millis() - began;
  float t = elapsed >= 2500 ? 1.0f : elapsed / 2500.0f;
  float f = t * t * (3 - 2 * t);

  for (byte i = 0; i < 4; i++) {
    pos[i] = src[i] + (int)((dst[i] - src[i]) * f);
    s[i].writeMicroseconds(pos[i]);
  }

  if (elapsed >= 2500) {
    moving = false;
    Serial.println("ARRIVED. Inspect before next n.");
    show();
  }
}

void moveTo(const int p[4], bool remember) {
  for (byte i = 0; i < 4; i++) {
    if (p[i] < lo[i] || p[i] > hi[i]) {
      Serial.println("ERR RANGE");
      return;
    }
  }

  for (byte i = 0; i < 4; i++) {
    src[i] = pos[i];
    dst[i] = p[i];
    if (remember) back[i] = pos[i];
  }

  began = millis();
  moving = true;
}

void command(char c) {
  if (c == 'e') {
    if (armed) return;

    for (byte i = 0; i < 4; i++) {
      pos[i] = back[i] = 1500;
      s[i].writeMicroseconds(1500);
      s[i].attach(pins[i]);
    }

    armed = true;
    moving = false;
    paused = false;
    stepNo = -1;
    Serial.println("Enabled at 1500. n opens lids first.");
    show();

  } else if (c == 'x') {
    for (byte i = 0; i < 4; i++) s[i].detach();
    armed = false;
    moving = false;
    paused = false;
    Serial.println("Signal OFF, not power OFF.");

  } else if (c == 'h') {
    updateMotion();
    moving = false;
    paused = true;
    Serial.println("HOLD: torque remains ON.");
    show();

  } else if (c == 'r') {
    if (!armed) return;
    updateMotion();
    moving = false;
    paused = true;
    moveTo(back, false);

  } else if (c == 'p') {
    show();

  } else if (c == 'n') {
    if (!armed || moving || paused) {
      Serial.println("Blocked: disabled, moving, or paused.");
      return;
    }

    if (stepNo >= 71) {
      Serial.println("END: half-range test only.");
      return;
    }

    stepNo++;
    byte corner = stepNo / 18;
    byte phase = stepNo % 18;
    int p[4] = {1500, 1500, 700, 2350};
    int leftClose = 0, rightClose = 0;

    if (phase >= 1 && phase <= 16) {
      p[0] = gaze[corner][0];
      p[1] = gaze[corner][1];
    }

    if (phase >= 2 && phase <= 5)
      rightClose = (phase - 1) * 25;

    if (phase >= 7 && phase <= 10)
      leftClose = (phase - 6) * 25;

    if (phase >= 12 && phase <= 15)
      leftClose = rightClose = (phase - 11) * 25;

    p[2] = 700 + 1350L * leftClose / 100;
    p[3] = 2350 - 1400L * rightClose / 100;

    Serial.print("STEP ");
    Serial.print(stepNo + 1);
    Serial.print("/72 gaze: ");
    Serial.print(p[0]);
    Serial.print(' ');
    Serial.println(p[1]);

    Serial.print("Closure L/R %: ");
    Serial.print(leftClose);
    Serial.print(' ');
    Serial.println(rightClose);

    moveTo(p, true);

  } else {
    Serial.println("e enable; n next; h hold;");
    Serial.println("r reverse; x off; p position");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("No signals at boot. Select Newline.");
  Serial.println("e immediately moves all servos to 1500.");
  command('?');
}

void loop() {
  for (byte n = 0; n < 24 && Serial.available(); n++) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      if (count == 1) command(input);
      else if (count > 1)
        Serial.println("Send one character per line.");
      count = 0;
    } else {
      input = c;
      if (count < 2) count++;
    }
  }

  unsigned long now = millis();
  if ((unsigned long)(now - tick) >= 20) {
    tick = now;
    updateMotion();
  }
}
