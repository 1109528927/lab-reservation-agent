-- 站内消息 / 信用流水 / 报修工单（闭环业务）
USE lab_access;

CREATE TABLE IF NOT EXISTS `user_message` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `msg_type` VARCHAR(40) NOT NULL COMMENT 'approve/reject/pass_expire/no_show/repair/system',
  `title` VARCHAR(120) NOT NULL,
  `content` VARCHAR(500) NOT NULL,
  `related_id` INT NULL COMMENT '关联预约/通行码/工单等',
  `is_read` TINYINT NOT NULL DEFAULT 0,
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_read` (`user_id`, `is_read`),
  KEY `idx_type_related` (`msg_type`, `related_id`),
  CONSTRAINT `fk_msg_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `credit_log` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `delta` INT NOT NULL COMMENT '正加负扣',
  `score_after` INT NOT NULL,
  `reason` VARCHAR(200) NOT NULL,
  `reservation_id` INT NULL,
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_credit_user` (`user_id`),
  CONSTRAINT `fk_credit_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `repair_ticket` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `lab_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `title` VARCHAR(120) NOT NULL,
  `description` VARCHAR(500) NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/processing/done',
  `admin_reply` VARCHAR(500) NULL,
  `handler_id` INT NULL,
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_repair_user` (`user_id`),
  KEY `idx_repair_status` (`status`),
  CONSTRAINT `fk_repair_lab` FOREIGN KEY (`lab_id`) REFERENCES `lab` (`id`),
  CONSTRAINT `fk_repair_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
