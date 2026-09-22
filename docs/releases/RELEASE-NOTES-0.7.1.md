# SAMA Open Display 0.7.1 Theme Selector

> 历史版本记录；功能和待办均以 0.7.1 发布时为准。现行状态见 [项目状态](../PROJECT.md)。

## Changes

- Keeps the Home page's `内容` section and renames its first content mode from
  `系统仪表盘` to `使用主题`.
- Adds a native WinUI theme selector with immediate preview refresh.
- Exposes enabled themes through the backend `theme-list` JSON command.
- Packages `系统仪表盘` as the preinstalled
  `io.github.sitbat.sama-open-display.system-dashboard` theme plugin.
- Declares the system dashboard's dependency on the read-only system metrics
  provider.
- Removes the SAMA Grid theme from the preinstalled plugin set.

## Validation

- 50 Python tests pass; one optional OpenCV test is skipped.
- WinUI Release build completes successfully.
- The folder release launches, discovers the preinstalled theme and provider,
  and renders a preview using the selected plugin theme.
