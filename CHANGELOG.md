# Changelog

## 0.1.0

- First public release: `INTRO.EXE`, `PS.EXE` and `AP.EXE` (CD version 1.2) reimplemented in C on SDL3, VGA with AdLib / Sound Blaster sound.
- AdLib through Nuked-OPL3, whatever sound device the install chose; EMS emulated; no copy protection.
- Game speed: 16 timer ticks per simulator frame by default (`--frame-ticks`), so the world runs in real time and the TIME SCALE slider works.
- Flaps: F lowers them a step, Shift+F raises them (the original's F cycles them).
- Key bindings: the flight keys can be changed in the launcher (`--keys`).
- Launcher: game folder, speed, aspect, window size, full screen, sound; File (Preferences with Always on top, Exit), Settings > Key Bindings, About.
- A gamepad works as the joystick; Alt+Enter switches to full screen.
