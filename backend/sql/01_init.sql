-- 智能实验室预约通行系统：基础库表（A0）
CREATE DATABASE IF NOT EXISTS lab_access
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE lab_access;

CREATE TABLE IF NOT EXISTS `user` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(50) NOT NULL,
  `password` VARCHAR(255) NOT NULL,
  `employee_no` VARCHAR(50) NOT NULL,
  `role` VARCHAR(20) NOT NULL DEFAULT 'student',
  `credit_score` INT NOT NULL DEFAULT 100 COMMENT '信用分，A3 使用',
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  UNIQUE KEY `uk_employee_no` (`employee_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `user_token` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `token` VARCHAR(255) NOT NULL,
  `expires_at` DATETIME NOT NULL,
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_token` (`token`),
  KEY `idx_user_id` (`user_id`),
  CONSTRAINT `fk_user_token_user`
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A1 预留：实验室（先建表，代码随后接）
CREATE TABLE IF NOT EXISTS `lab` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(100) NOT NULL,
  `location` VARCHAR(200) NULL,
  `capacity` INT NOT NULL DEFAULT 20,
  `need_approve` TINYINT NOT NULL DEFAULT 1 COMMENT '1=人工审批 0=自动通过',
  `status` VARCHAR(20) NOT NULL DEFAULT 'open' COMMENT 'open/closed',
  `description` VARCHAR(500) NULL,
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_lab_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A1 预留：预约
CREATE TABLE IF NOT EXISTS `reservation` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `lab_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `start_time` DATETIME NOT NULL,
  `end_time` DATETIME NOT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
  `purpose` VARCHAR(300) NULL,
  `reject_reason` VARCHAR(300) NULL,
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_lab_time` (`lab_id`, `start_time`, `end_time`),
  KEY `idx_user` (`user_id`),
  CONSTRAINT `fk_res_lab` FOREIGN KEY (`lab_id`) REFERENCES `lab` (`id`),
  CONSTRAINT `fk_res_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A2：须知 / 凭证 / 流水（亦见 03_access.sql）
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
  `status` VARCHAR(20) NOT NULL DEFAULT 'active',
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
