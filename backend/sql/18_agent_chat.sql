-- 助手聊天记录（业务库，切屏可回看；MemorySaver 仍负责图内短期记忆）
USE lab_access;

CREATE TABLE IF NOT EXISTS `agent_chat_message` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `thread_id` VARCHAR(64) NOT NULL,
  `role` VARCHAR(20) NOT NULL COMMENT 'user/assistant',
  `content` TEXT NOT NULL,
  `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_agent_chat_user_thread` (`user_id`, `thread_id`, `id`),
  CONSTRAINT `fk_agent_chat_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
