# Changelog

## 0.1.1

- The CD-ROM version 1.2 is linked at the Internet Archive (https://archive.org/details/acesot-p) in the README and `HOW TO RUN.txt`; in the launcher, clicking the warning sign beside a missing-files or other-release note opens that page.
- Game files of another release (the floppy versions 1.0, 1.01 and 1.2 / Patch B, the WWII: 1946 expansion disk) are recognised: the launcher and the game say which release the folder holds and that the CD-ROM version 1.2 is needed, before anything runs (the game used to stop with the loader's sizes, the launcher let it start).
- A picture that isn't changing is drawn again after Alt+Enter, a window resize or the window being uncovered (it used to keep the old full-screen picture, cropped, after switching back to a window).

## 0.1.0

- First public release: `INTRO.EXE`, `PS.EXE` and `AP.EXE` (CD version 1.2) reimplemented in C on SDL3, VGA with AdLib / Sound Blaster sound.
- AdLib through Nuked-OPL3, whatever sound device the install chose; EMS emulated; no copy protection.
- Game speed: 16 timer ticks per simulator frame by default (`--frame-ticks`), so the world runs in real time and the TIME SCALE slider works.
- Flaps: F lowers them a step, Shift+F raises them (the original's F cycles them).
- Key bindings: the flight keys can be changed in the launcher (`--keys`).
- Launcher: game folder, speed, aspect, window size, full screen, sound; File (Preferences with Always on top, Exit), Settings > Key Bindings, About.
- A gamepad works as the joystick; Alt+Enter switches to full screen.
