# Exhibition snapshot saved 2026-11-19

Preserves the application and paired Arduino firmware that the user tested successfully on 2026-11-18. Saving this snapshot does not launch the application or upload firmware.

English startup: scripts/run.command --config config.en.toml. Chinese startup: scripts/run.command --config config.toml. Production page: http://127.0.0.1:8765 . Port 8878 serves a separate visual sample, not the live conversation. Existing local memories are preserved; runtime memories, credentials and virtual environments are not included on GitHub.

Firmware source: hardware/current-20261021/ThreePuppets_SerialPerformance, with the adjacent PuppetEyes library. The application HEX in firmware/ was recompiled and verified byte-for-byte identical to the last tested upload. SHA-256 values are in manifest.json. Temporary single-axis test sketches are not the production firmware.

## Retained behavior

Dog left 100%, bird right 100%, mouse 50% per channel. Straight eye offsets reduced approximately 5%; diagonal offsets reduced approximately 15% total. Dog right eyelid opening: 2090us. Full table: docs/hardware/current-ranges.zh.md.

Dog yaw D7 retains the tested disabled state; it has NOT been re-enabled. The user is leaving this servo disconnected. Keep its power and signal disconnected. All other eye, body and dialogue behavior remains as tested.

Serial: 115200, /dev/cu.usbmodem31201, relay active HIGH. Close the Arduino IDE serial monitor before startup. Ctrl-C stops audio and body movement; enabled eye servos retain their last commanded pose, which is not a servo power cutoff.

## Validation and limits

69 relevant Python tests passed using an empty serial-port override for isolation. Browser audio and six visual JavaScript test files passed. The actual eye driver is tested in both dog-yaw-disabled and enabled builds, including all directions, 972 ordered transitions, pulse bounds and no D7 pulses when disabled. Uno firmware recompiles successfully and matches the tested HEX.

The complete Python suite is NOT green: one broad run had 105 passes and 3 failures before interruption (startup readiness, long-term memory changes, disabled observation cleanup). Existing tests include assumptions inconsistent with current configuration. Application behavior was not changed to satisfy those tests. No live hardware motion test was performed during this save operation.
