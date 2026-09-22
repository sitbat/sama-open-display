# SAMA Open Display 0.7.0 WinUI Preview

> 历史版本记录；功能和待办均以 0.7.0 发布时为准。现行状态见 [项目状态](../PROJECT.md)。

## Highlights

- First real C# WinUI 3 frontend using Windows App SDK 2.5.1 and .NET 10.
- Native NavigationView, Mica backdrop, system theme support, Windows typography,
  ContentDialog, InfoBar, cards, and modern file picker.
- Dedicated Display, Plugin Center, Settings, and About pages.
- Python core exposed through a JSON command-line boundary instead of duplicating
  protocol or plugin logic in the frontend.
- Plugin Center supports batch installation, enable, disable, uninstall,
  dependencies, and permission display.
- Folder-based deployment: the main EXE, Windows App SDK/.NET DLLs, Python
  backend, plugins, configuration, and documentation remain separate files.

## Migration status

Read-only device detection, dashboard preview, and plugin management are active.
Hardware writes are intentionally disabled in the WinUI preview until the
confirmation and device-identity flow receives a separate migration test. The
classic Python GUI remains available for verified hardware sending.

## Validation

- WinUI Release build completed successfully with no compiler errors.
- 49 Python tests pass; one optional OpenCV test is skipped in the lightweight build.
- WinUI application launched successfully and generated a backend dashboard preview.
