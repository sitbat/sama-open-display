# SAMA Open Display 0.9.0 Continuous Dashboard Preview

## Changes

- Adds confirmed start and explicit stop controls for the WinUI continuous
  dashboard.
- Uses the selected built-in or installed theme and permission-scoped provider
  data for every frame.
- Keeps exact protocol identity verification and the explicit hardware-write
  gate for every run.
- Sends one OEM-format full baseline, then uses hardware-validated `CC` deltas
  at a 0.5-second target interval without queueing frames faster than the link.
- Stops through a control signal checked between transfer blocks, then closes
  the serial port through the normal backend cleanup path.
- Uses the recovered 720x1568 scan mapping and frame sequence beginning at zero.

## Validation status

- 55 automated tests pass and the Release WinUI build completes.
- The one-shot WinUI transfer is physically verified.
- The 120x80 `CC` probe completed in about 0.1 seconds and displayed correctly.
- Two 12-frame continuous dashboard runs completed at about 1.7 FPS without
  flicker or corruption, confirmed on the ROM 1.91 physical display.
