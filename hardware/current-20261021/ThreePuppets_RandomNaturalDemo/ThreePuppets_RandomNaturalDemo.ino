#include <PuppetEyes.h>

PuppetEyes eyes;
// 一轮12张动作卡：每个角色都展示四种模式，打乱顺序后连续播放。
// 0=眨眼+快，1=不眨眼+快，2=眨眼+缓慢，3=不眨眼+缓慢。
byte deck[12];
byte nextCard = 12;
bool playing = true;
bool waiting = false;
bool reshuffle = false;
unsigned long waitStarted = 0;
unsigned long waitMs = 0;
Gaze previous[3] = {Gaze::Center, Gaze::Center, Gaze::Center};
const Gaze ALL_DIRECTIONS[] = {
  Gaze::Center, Gaze::Left, Gaze::Right, Gaze::Up, Gaze::Down,
  Gaze::UpperLeft, Gaze::UpperRight, Gaze::LowerLeft, Gaze::LowerRight
};
const Gaze MOUSE_DIRECTIONS[] = {Gaze::Center, Gaze::Left, Gaze::Right};

void shuffleDeck() {
  for (byte i = 0; i < 12; i++) deck[i] = i;
  for (byte i = 11; i > 0; i--) {
    byte j = random(i + 1);
    byte value = deck[i]; deck[i] = deck[j]; deck[j] = value;
  }
  nextCard = 0;
  Serial.println("NEW ROUND: 3 puppets x 4 modes, shuffled");
}

void setup() {
  Serial.begin(115200);
  // A2未接线，用于给随机顺序提供种子。
  randomSeed(analogRead(A2) ^ micros());
  eyes.begin();
  Serial.println("Random demo: G play, P pause after current action, T reshuffle");
}

void loop() {
  eyes.update(); // 使用驱动时，每次loop都要调用。
  while (Serial.available() > 0) {
    char key = Serial.read();
    if (key == 'p' || key == 'P') {
      playing = false;
      Serial.println("PAUSE after current action; G resumes.");
    }
    if (key == 'g' || key == 'G') playing = true;
    if (key == 't' || key == 'T') {
      playing = true;
      reshuffle = true;
    }
  }
  if (eyes.isBusy()) {
    waiting = false;
    return;
  }
  if (!playing) return;
  if (reshuffle) {
    nextCard = 12;
    waiting = false;
    reshuffle = false;
  }
  if (!waiting) {
    waiting = true;
    waitStarted = millis();
    waitMs = random(900, 2201);
    return;
  }
  if ((unsigned long)(millis() - waitStarted) < waitMs) return;
  if (nextCard == 12) shuffleDeck();
  byte card = deck[nextCard++];
  byte character = card / 4;
  byte mode = card % 4;
  Gaze direction;
  do {
    direction = character == 1 ? MOUSE_DIRECTIONS[random(3)]
                               : ALL_DIRECTIONS[random(9)];
  } while (direction == previous[character]);
  Blink blink = (mode == 0 || mode == 2) ? Blink::Yes : Blink::No;
  Speed speed = mode < 2 ? Speed::Fast : Speed::Smooth;
  if (eyes.look(static_cast<Puppet>(character), direction, blink, speed)) {
    previous[character] = direction;
    Serial.print(character == 0 ? "Bird" : character == 1 ? "Mouse" : "Dog");
    Serial.print(" | gaze="); Serial.print(static_cast<byte>(direction));
    Serial.print(blink == Blink::Yes ? " | blink" : " | no blink");
    Serial.println(speed == Speed::Fast ? " | fast" : " | smooth");
  }
  waiting = false;
}
