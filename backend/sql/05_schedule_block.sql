-- 教务排课占档（仅学校管理员维护）
USE lab_access;

CREATE TABLE IF NOT EXISTS `lab_schedule_block` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `lab_id` INT NOT NULL,
  `title` VARCHAR(200) NOT NULL COMMENT '课程名',
  `start_time` DATETIME NOT NULL,
  `end_time` DATETIME NOT NULL,
  `source` VARCHAR(20) NOT NULL DEFAULT 'manual' COMMENT 'manual/excel/agent',
  `created_by` INT NULL,
  `note` VARCHAR(300) NULL,
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_lab_time` (`lab_id`, `start_time`, `end_time`),
  CONSTRAINT `fk_block_lab` FOREIGN KEY (`lab_id`) REFERENCES `lab` (`id`),
  CONSTRAINT `fk_block_user` FOREIGN KEY (`created_by`) REFERENCES `user` (`id`)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
