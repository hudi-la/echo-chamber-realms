#ifndef PUPPET_EYES_H
#define PUPPET_EYES_H
#include <Arduino.h>
#include <Servo.h>

// 所有左右都以木偶本人为准。老鼠没有眼球上下轴，上/下映射为平视。
enum class Puppet : uint8_t { Bird, Mouse, Dog };
enum class Gaze : uint8_t {
  Center, Left, Right, Up, Down, UpperLeft, UpperRight, LowerLeft, LowerRight
};
enum class Blink : uint8_t { No, Yes };
enum class Speed : uint8_t { Fast, Smooth };

class PuppetEyes {
public:
  void begin();
  void head(int microseconds);
  // 每次 loop 必须调用；正常动作不使用 delay，不妨碍其他代码工作。
  void update();
  // 同一角色忙碌时返回 false，不插队。不同角色可独立调用。
  bool look(Puppet puppet, Gaze gaze, Blink blink = Blink::Yes,
            Speed speed = Speed::Fast);
  bool isBusy(Puppet puppet) const;
  bool isBusy() const;

private:
  enum Phase : uint8_t { Idle, LevelBeforeBlink, Closing, Moving, Settling };
  struct Motion {
    Phase phase = Idle;
    unsigned long started = 0;
    int yaw = 1500, pitch = 1500;
    int fromYaw = 1500, fromPitch = 1500;
    int toYaw = 1500, toPitch = 1500;
    Speed speed = Speed::Fast;
  };
  Servo motors[11];
  Motion motion[3];
  bool ready = false;
  void openLids(uint8_t p);
  void closeLids(uint8_t p);
  void restLids(uint8_t p);
  void writeEyes(uint8_t p);
  void startMove(uint8_t p);
  void startBlink(uint8_t p);
};
#endif
