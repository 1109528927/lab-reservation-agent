USE lab_access;

-- 若旧库 user 表缺信用分列可执行：
-- ALTER TABLE `user` ADD COLUMN `credit_score` INT NOT NULL DEFAULT 100 COMMENT '信用分' AFTER `role`;

CREATE TABLE IF NOT EXISTS `safety_ack` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `reservation_id` INT NOT NULL,
  `version` VARCHAR(20) NOT NULL DEFAULT 'v1',
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_res` (`user_id`, `reservation_id`),
  CONSTRAINT `fk_ack_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_ack_res` FOREIGN KEY (`reservation_id`) REFERENCES `reservation` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `passcode` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(64) NOT NULL,
  `reservation_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT 'active/used/revoked/expired',
  `valid_from` DATETIME NOT NULL,
  `valid_to` DATETIME NOT NULL,
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code` (`code`),
  KEY `idx_res` (`reservation_id`),
  CONSTRAINT `fk_pc_res` FOREIGN KEY (`reservation_id`) REFERENCES `reservation` (`id`),
  CONSTRAINT `fk_pc_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `access_log` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(64) NULL,
  `device_id` VARCHAR(64) NULL,
  `user_id` INT NULL,
  `reservation_id` INT NULL,
  `allowed` TINYINT NOT NULL DEFAULT 0,
  `reason` VARCHAR(200) NULL,
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_created` (`create_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
