-- 登录页「忘记密码」申请：用户提交后管理员处理
USE lab_access;

CREATE TABLE IF NOT EXISTS `password_reset_request` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(50) NOT NULL COMMENT '登录账号',
  `employee_no` VARCHAR(50) NULL COMMENT '学号/工号（可空）',
  `contact` VARCHAR(120) NULL COMMENT '申请人联系方式（手机/QQ等）',
  `reason` VARCHAR(500) NULL COMMENT '说明',
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/done/rejected',
  `handler_id` INT NULL,
  `admin_note` VARCHAR(500) NULL,
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_pwd_reset_status` (`status`),
  KEY `idx_pwd_reset_created` (`create_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
