# SAMA Open Display 0.8.0 WinUI Hardware Gate

> 历史版本记录；功能和待办均以 0.8.0 发布时为准。现行状态见 [项目状态](../PROJECT.md)。

## Changes

- Enables the WinUI `发送当前画面` button only after read-only USB detection
  and a valid local preview are both available.
- Shows the detected COM port, USB VID/PID, selected brightness and required
  protocol identity in a confirmation dialog before every transfer.
- Reuses the proven Python transfer core and its explicit `--write-hardware`
  gate instead of duplicating protocol code in C#.
- Performs a HELLO handshake and requires the exact verified identity
  `chs_65inch.dev1_rom1.91` before sending frame data.
- Reports transfer success or failure in the WinUI page.
- Keeps continuous dashboard sending disabled until the new one-shot flow is
  verified on the physical display.

## Validation

- The build and automated tests do not write to hardware.
- A physical transfer requires a user click followed by confirmation in the
  WinUI dialog.
- The user verified a complete one-shot transfer on the physical SAMA display.
