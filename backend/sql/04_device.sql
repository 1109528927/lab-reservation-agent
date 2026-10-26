USE lab_access;

-- 门禁设备：一块硬件对应一个实验室
CREATE TABLE IF NOT EXISTS `access_device` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `device_id` VARCHAR(64) NOT NULL COMMENT '硬件上报的设备号',
  `lab_id` INT NOT NULL,
  `name` VARCHAR(100) NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT 'active/disabled',
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_device_id` (`device_id`),
  CONSTRAINT `fk_device_lab` FOREIGN KEY (`lab_id`) REFERENCES `lab` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 演示：两间实验室各绑一台模拟设备（与种子实验室 id 对应，请按实际 lab.id 调整）
INSERT INTO access_device (device_id, lab_id, name, status)
SELECT 'ESP32-LAB-1', id, '嵌入式实验室门禁', 'active' FROM lab WHERE name='嵌入式实验室 A'
ON DUPLICATE KEY UPDATE lab_id=VALUES(lab_id), name=VALUES(name);

INSERT INTO access_device (device_id, lab_id, name, status)
SELECT 'ESP32-LAB-2', id, '网络实验室门禁', 'active' FROM lab WHERE name='网络实验室'
ON DUPLICATE KEY UPDATE lab_id=VALUES(lab_id), name=VALUES(name);

-- 兼容旧模拟门默认设备号：绑到网络实验室（可改）
INSERT INTO access_device (device_id, lab_id, name, status)
SELECT 'SIM-DOOR-01', id, '网页模拟门（网络实验室）', 'active' FROM lab WHERE name='网络实验室'
ON DUPLICATE KEY UPDATE name=VALUES(name);
