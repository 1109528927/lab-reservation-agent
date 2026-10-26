-- 演示数据（先执行 01_init.sql，再通过注册接口创建用户）
-- 管理员：UPDATE user SET role='admin' WHERE username='你的账号';
-- 老师账号推荐用：python scripts/seed_teacher.py  → teacher / 123456
-- 公开注册接口强制 role=student，不能自提权为 admin/teacher

USE lab_access;


INSERT INTO lab (name, location, capacity, need_approve, status, description)
VALUES
  ('嵌入式实验室 A', '教学楼 B301', 30, 1, 'open', '嵌入式 / 传感器实验'),
  ('网络实验室', '教学楼 B205', 40, 0, 'open', '自动审批，适合课程上机')
ON DUPLICATE KEY UPDATE location=VALUES(location);
