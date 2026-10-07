-- version: 1.4.0
-- title: 调度运行状态

-- seq: 1
-- model: schedule_run_state
-- action: create
-- summary: 每个任务一行，记录日期间隔、下次运行日期、最近一次成功的日期窗口和运行时长
CREATE TABLE IF NOT EXISTS schedule_run_state (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_id BIGINT UNSIGNED NOT NULL COMMENT '任务ID',
  date_interval INT NOT NULL DEFAULT 1 COMMENT '每次运行覆盖的天数，含开始和结束当天',
  next_start_date VARCHAR(8) NOT NULL DEFAULT '' COMMENT '下次运行开始日期 YYYYMMDD',
  next_end_date VARCHAR(8) NOT NULL DEFAULT '' COMMENT '下次运行结束日期 YYYYMMDD',
  last_success_start VARCHAR(8) NOT NULL DEFAULT '' COMMENT '最近一次成功的开始日期',
  last_success_end VARCHAR(8) NOT NULL DEFAULT '' COMMENT '最近一次成功的结束日期',
  last_duration_ms BIGINT NULL COMMENT '最近一次成功的运行时长毫秒',
  last_row_count INT NULL COMMENT '最近一次成功写入的行数',
  last_success_at DATETIME NULL COMMENT '最近一次成功的完成时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_job (job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='调度运行状态';
