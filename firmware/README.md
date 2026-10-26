# 门口终端固件

工程目录：`firmware/esp32s3_door/`

## 环境

- Arduino IDE + ESP32 板卡包（推荐乐鑫 `esp32@2.0.17` 国内镜像）
- 开发板：**ESP32S3 Dev Module**
- 打开 `esp32s3_door/esp32s3_door.ino` 编译烧录

## 配置

编辑 `esp32s3_door/config.h`：

- `WIFI_SSID` / `WIFI_PASSWORD`：现场 Wi-Fi
- `VERIFY_URL`：后端核验地址，例如 `http://<电脑局域网IP>:8000/api/access/verify`
- `DEVICE_ID`：与库表 `access_device.device_id` 一致

## 行为简述

串口二维码扫码模块（GM65 等同款 TTL）经 UART 把码送给 ESP32-S3，固件 `POST /api/access/verify`，再驱动指示灯与蜂鸣器。

断网时先查本地已缓存通行码，再查应急主码；都不命中则拒绝。
