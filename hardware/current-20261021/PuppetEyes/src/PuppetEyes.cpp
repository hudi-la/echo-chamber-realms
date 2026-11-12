#include "PuppetEyes.h"

namespace {
// 按实际接线排序，不使用D0/D1；D12/D13直流电机保持关闭。
const uint8_t PINS[11] = {A0, A1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
const uint8_t NONE = 255;
struct Calibration {
  uint8_t yaw, pitch, lidL, lidR;
  int left, right, up, down;
  int openL, closedL, restL, openR, closedR, restR;
};
// 角色顺序：鸟、老鼠、狗。左右已按2026-10-20现场确认，以木偶本人为准。
// 改接线或行程时只修改这里。老鼠D10抬头轴保持1500，不作为眼球上下轴。
const Calibration CAL[3] = {
  // 2026-11-11：上眼皮全开有异响，两侧全开位置各向闭合方向收回50μs，待现场复核。
  // 2026-11-11：自身左看有异响，左端点从2050收回至2000，待现场复核。
  // 2026-11-11后续：仍反馈眼皮异响，全开位置再各收回50μs至825/2250，待现场复核。
  // 2026-11-11：左看、下看异响，分别再收回50μs至1950/1155，待现场复核。
  {3, 2, 0, 1, 1950, 1050, 2150, 1155, 825, 2050, 1425, 2250, 950, 1600},
  {8, NONE, 9, NONE, 1300, 1650, 1500, 1500, 1450, 2000, 1450, 0, 0, 0},
  // 2026-11-11：自身右看有异响，右端点从900收回至950，待现场复核。
  // 2026-11-11：上看有异响，来源未确认；先将眼球上端点1900收回至1850，待现场复核。
  // 2026-11-11：用户怀疑狗眼皮全开有异响，两侧各向闭合方向收回50μs，待现场复核。
  // 2026-11-11：自身左看有轻微异响，左端点2000收回至1950，待现场复核。
  // 2026-11-11：右看仍有轻微异响，右端点950再收回至1000，待现场复核。
  {7, 6, 4, 5, 1950, 1000, 1850, 1100, 900, 2200, 1500, 2150, 850, 1500}
};
const unsigned long LEVEL_MS = 450;
const unsigned long BLINK_MS = 180;
const unsigned long SMOOTH_MS = 1200;
const unsigned long SETTLE_MS = 400;
}

void PuppetEyes::openLids(uint8_t p) {
  const Calibration &c = CAL[p];
  motors[c.lidL].writeMicroseconds(c.openL);
  if (c.lidR != NONE) motors[c.lidR].writeMicroseconds(c.openR);
}
void PuppetEyes::closeLids(uint8_t p) {
  const Calibration &c = CAL[p];
  motors[c.lidL].writeMicroseconds(c.closedL);
  if (c.lidR != NONE) motors[c.lidR].writeMicroseconds(c.closedR);
}
void PuppetEyes::restLids(uint8_t p) {
  // 眼球仍朝上时保留眼皮全开，避免降下眼皮遮挡机构。
  if (motion[p].pitch > 1500) { openLids(p); return; }
  const Calibration &c = CAL[p];
  motors[c.lidL].writeMicroseconds(c.restL);
  if (c.lidR != NONE) motors[c.lidR].writeMicroseconds(c.restR);
}
void PuppetEyes::writeEyes(uint8_t p) {
  const Calibration &c = CAL[p];
  motors[c.yaw].writeMicroseconds(motion[p].yaw);
  if (c.pitch != NONE) motors[c.pitch].writeMicroseconds(motion[p].pitch);
}

void PuppetEyes::begin() {
  if (ready) return;
  // Relay pins are configured by the serial sketch only after polarity is known.
  // 启动时先启用眼皮全开，再启用眼球回正。仅初始化包含等待。
  for (uint8_t p = 0; p < 3; p++) {
    const Calibration &c = CAL[p];
    openLids(p);
    motors[c.lidL].attach(PINS[c.lidL]);
    if (c.lidR != NONE) motors[c.lidR].attach(PINS[c.lidR]);
  }
  delay(900);
  for (uint8_t p = 0; p < 3; p++) {
    const Calibration &c = CAL[p];
    motion[p] = Motion();
    writeEyes(p);
    motors[c.yaw].attach(PINS[c.yaw]);
    if (c.pitch != NONE) motors[c.pitch].attach(PINS[c.pitch]);
  }
  motors[10].writeMicroseconds(1500);
  motors[10].attach(PINS[10]);
  delay(700);
  for (uint8_t p = 0; p < 3; p++) restLids(p);
  ready = true;
}

bool PuppetEyes::isBusy(Puppet puppet) const {
  uint8_t p = static_cast<uint8_t>(puppet);
  return p < 3 && motion[p].phase != Idle;
}
bool PuppetEyes::isBusy() const {
  for (uint8_t p = 0; p < 3; p++) if (motion[p].phase != Idle) return true;
  return false;
}

void PuppetEyes::startBlink(uint8_t p) {
  closeLids(p);
  motion[p].phase = Closing;
  motion[p].started = millis();
}
void PuppetEyes::startMove(uint8_t p) {
  Motion &m = motion[p];
  // 睁眼和转眼同阶段发起。缓慢模式只插值眼球，眨眼保持短促。
  openLids(p);
  m.fromYaw = m.yaw;
  m.fromPitch = m.pitch;
  m.started = millis();
  if (m.speed == Speed::Fast) {
    m.yaw = m.toYaw;
    m.pitch = m.toPitch;
    writeEyes(p);
    m.phase = Settling;
  } else m.phase = Moving;
}

bool PuppetEyes::look(Puppet puppet, Gaze gaze, Blink blink, Speed speed) {
  uint8_t p = static_cast<uint8_t>(puppet);
  if (!ready || p >= 3 || isBusy(puppet) || static_cast<uint8_t>(gaze) > 8)
    return false;
  const Calibration &c = CAL[p];
  Motion &m = motion[p];
  m.toYaw = 1500;
  m.toPitch = 1500;
  if (gaze == Gaze::Left || gaze == Gaze::UpperLeft || gaze == Gaze::LowerLeft)
    m.toYaw = c.left;
  if (gaze == Gaze::Right || gaze == Gaze::UpperRight || gaze == Gaze::LowerRight)
    m.toYaw = c.right;
  if (gaze == Gaze::Up || gaze == Gaze::UpperLeft || gaze == Gaze::UpperRight)
    m.toPitch = c.up;
  if (gaze == Gaze::Down || gaze == Gaze::LowerLeft || gaze == Gaze::LowerRight)
    m.toPitch = c.down;
  m.speed = speed;
  if (blink == Blink::Yes) {
    if (m.pitch > 1500) {
      // 已经仰视时，先保持眼皮打开并回平视，再闭眼。
      openLids(p);
      m.pitch = 1500;
      writeEyes(p);
      m.phase = LevelBeforeBlink;
      m.started = millis();
    } else startBlink(p);
  } else startMove(p);
  return true;
}

void PuppetEyes::update() {
  if (!ready) return;
  unsigned long now = millis();
  for (uint8_t p = 0; p < 3; p++) {
    Motion &m = motion[p];
    unsigned long elapsed = now - m.started;
    switch (m.phase) {
      case LevelBeforeBlink:
        if (elapsed >= LEVEL_MS) startBlink(p);
        break;
      case Closing:
        if (elapsed >= BLINK_MS) startMove(p);
        break;
      case Moving: {
        float t = elapsed >= SMOOTH_MS ? 1.0f : (float)elapsed / SMOOTH_MS;
        float f = t * t * (3.0f - 2.0f * t);
        m.yaw = m.fromYaw + (int)((m.toYaw - m.fromYaw) * f);
        m.pitch = m.fromPitch + (int)((m.toPitch - m.fromPitch) * f);
        writeEyes(p);
        if (elapsed >= SMOOTH_MS) {
          m.phase = Settling;
          m.started = now;
        }
        break;
      }
      case Settling:
        if (elapsed >= SETTLE_MS) {
          restLids(p);
          m.phase = Idle;
        }
        break;
      case Idle: break;
    }
  }
}

void PuppetEyes::head(int microseconds) {
  if (ready) motors[10].writeMicroseconds(constrain(microseconds, 1500, 1650));
}
