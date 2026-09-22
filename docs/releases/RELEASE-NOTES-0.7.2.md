# SAMA Open Display 0.7.2 Stable Theme Picker

> 历史版本记录；功能和待办均以 0.7.2 发布时为准。现行状态见 [项目状态](../PROJECT.md)。

## Changes

- Keeps the `内容` section and its `使用主题` content mode.
- Uses a fixed-height, single-line WinUI ComboBox presentation so opening or
  changing the theme selector no longer shifts the surrounding card layout.
- Keeps the theme description area at a stable height.
- Ignores stale asynchronous preview results when themes are changed quickly.
- Uses the built-in themes by default and no longer preinstalls any theme plugin.
- Keeps the read-only system metrics provider as the only bundled plugin.

## Validation

- 50 Python tests pass; one optional OpenCV test is skipped.
- WinUI Release build completes successfully.
- The release launches, lists built-in themes and renders their previews.
