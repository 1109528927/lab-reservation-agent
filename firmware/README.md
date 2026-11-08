# 门口终端固件

工程目录：`firmware/esp32s3_door/`

本机编译环境（免费）装在 `D:\edu_ruanjian`：双击 `启动ArduinoIDE.bat`，打开本目录下 `esp32s3_door.ino`，开发板选 **ESP32S3 Dev Module**。板卡包用乐鑫国内镜像装的 `esp32@2.0.17-cn`（不要选无 `-cn` 的国际版）。说明见 `D:\edu_ruanjian\README.md`。

真机接线 / **USB CDC On Boot** / 波特率踩坑见：`docs/15-ESP32门口接线与烧录笔记.md`。  
**从 0 到 1 完整步骤**（推荐按这个做）：`docs/步骤.md`。

本期验收是手机热点与局域网下的端到端原型：串口二维码扫码模块经 UART 把码送给 ESP32-S3，固件向电脑上的后端 `POST /api/access/verify`，再调用独立函数点亮指示灯并驱动蜂鸣器。模块可用 GM65 或同规格 TTL 平替。

网络链路是抽象接口。当前实现是 Wi-Fi。4G 的 UART 引脚和空实现只表示以后可以换链路，不在本期必须演示。

断网时先查本地已缓存的通行码，再查应急主码。都不命中则长鸣并亮拒绝灯。应急主码可用串口监视器以外的方式写入存储键 `master`，或在后续管理接口下发后调用 `whitelistSetMaster`。
