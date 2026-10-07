-- version: 1.2.0
-- title: 调度任务组

-- seq: 1
-- model: schedule_group
-- action: create
-- summary: 任务组配置表，一组任务共用调度；组间顺序用 sort_order，上一组成功后可接续运行
CREATE TABLE IF NOT EXISTS schedule_group (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL COMMENT '任务组名称',
  cron VARCHAR(64) NOT NULL DEFAULT '' COMMENT '组调度 cron，为空则只在上一组成功后或手动运行',
  sort_order INT NOT NULL DEFAULT 0 COMMENT '组间调度顺序，小的先执行',
  follow_previous TINYINT(1) NOT NULL DEFAULT 0 COMMENT '紧邻的上一启用组成功后自动接着运行',
  stop_on_failure TINYINT(1) NOT NULL DEFAULT 1 COMMENT '组内任务失败后停止后续任务',
  enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  last_status VARCHAR(16) NOT NULL DEFAULT '' COMMENT '最近一次运行状态',
  last_run_at DATETIME NULL COMMENT '最近一次运行开始时间',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_sort (sort_order, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='调度任务组';

-- seq: 2
-- model: schedule_group_run
-- action: create
-- summary: 任务组运行记录，区分定时、手动和上一组成功后的接续触发
CREATE TABLE IF NOT EXISTS schedule_group_run (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  group_id BIGINT UNSIGNED NOT NULL COMMENT '任务组ID',
  trigger_type VARCHAR(16) NOT NULL DEFAULT 'cron' COMMENT 'cron/manual/chain',
  started_at DATETIME NOT NULL COMMENT '开始时间',
  finished_at DATETIME NULL COMMENT '结束时间',
  status VARCHAR(16) NOT NULL DEFAULT 'running' COMMENT 'running/success/failed',
  message VARCHAR(500) NOT NULL DEFAULT '' COMMENT '结果或错误信息',
  PRIMARY KEY (id),
  KEY idx_group (group_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务组运行记录';

-- seq: 3
-- model: schedule_job
-- action: alter
-- summary: 任务可归入任务组；归入后按组调度，组内用 sort_order 决定先后
ALTER TABLE schedule_job
  ADD COLUMN group_id BIGINT UNSIGNED NULL COMMENT '所属任务组，为空表示单独调度' AFTER timeout,
  ADD COLUMN sort_order INT NOT NULL DEFAULT 0 COMMENT '组内调度顺序，小的先执行' AFTER group_id,
  ADD KEY idx_group_sort (group_id, sort_order, id);

-- seq: 4
-- model: schedule_run
-- action: alter
-- summary: 任务运行记录可关联到一次任务组运行
ALTER TABLE schedule_run
  ADD COLUMN group_run_id BIGINT UNSIGNED NULL COMMENT '所属任务组运行，单独调度时为空' AFTER job_id;
