USE lab_access;

-- 一台门禁设备绑定一个实验室（一块 ESP32 对应一间房）
CREATE TABLE IF NOT EXISTS `access_device` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `device_id` VARCHAR(64) NOT NULL COMMENT '硬件上报的 device_id',
  `lab_id` INT NOT NULL,
  `name` VARCHAR(100) NULL COMMENT '门口名称',
  `status` VARCHAR(20) NOT NULL DEFAULT 'active',
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_device` (`device_id`),
  KEY `idx_lab` (`lab_id`),
  CONSTRAINT `fk_dev_lab` FOREIGN KEY (`lab_id`) REFERENCES `lab` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 演示：两间实验室各绑一台模拟门（真机换成 ESP32 的 device_id）
INSERT INTO access_device (device_id, lab_id, name, status)
SELECT 'DOOR-LAB-1', id, CONCAT(name, '门口'), 'active' FROM lab WHERE id = 1
ON DUPLICATE KEY UPDATE lab_id=VALUES(lab_id), name=VALUES(name);

INSERT INTO access_device (device_id, lab_id, name, status)
SELECT 'DOOR-LAB-2', id, CONCAT(name, '门口'), 'active' FROM lab WHERE id = 2
ON DUPLICATE KEY UPDATE lab_id=VALUES(lab_id), name=VALUES(name);
