# 真机验证记录

这里按实验阶段保存当时的观察、传输日志和分析。它们是历史证据，部分早期方案已被后续测试修正。当前可用的编码与坐标结论见 [PROTOCOL.md](../../PROTOCOL.md)。记录中的 COM4/COM5 是测试时的端口号。

| 阶段 | 记录 |
| --- | --- |
| 握手 | [HELLO 返回](HANDSHAKE-VERIFIED.txt) |
| 全帧与方向 | [第一次测试卡传输](TEST-CARD-TRANSFER.txt)、[方向分析](ORIENTATION-ANALYSIS.md)、[第二次画面分析](SECOND-TEST-ANALYSIS.md)、[旋转后测试卡传输](TEST-CARD-ROTATED-TRANSFER.txt)、[横屏传输](LANDSCAPE-TEST-TRANSFER.txt) |
| 完整画面 | [验证汇总](HARDWARE-VALIDATION.md)、[连续仪表盘日志](LIVE-DASHBOARD-TEST.txt) |
| 差分更新 | [测试计划](PARTIAL-UPDATE-PLAN.md)、[首次传输](PARTIAL-UPDATE-TRANSFER.txt)、[结果分析](PARTIAL-UPDATE-RESULT.md) |

早期全帧验证使用过与后来原厂程序调用链不同的 `C8` 头；首次矩形差分实验也未得到正确画面。这些原始记录按测试时状态保留，不能直接当作现行发送参数使用。
