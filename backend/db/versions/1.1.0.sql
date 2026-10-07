-- version: 1.1.0
-- title: 监控调度平台

-- seq: 1
-- model: schedule_job
-- action: create
-- summary: 调度任务配置表，保存接口、入参、字段、cron、目标表、重试与水位线
CREATE TABLE IF NOT EXISTS schedule_job (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL COMMENT '任务名称',
  doc_id VARCHAR(20) NOT NULL COMMENT '接口文档编号',
  api_name VARCHAR(64) NOT NULL COMMENT '接口名',
  source VARCHAR(16) NOT NULL DEFAULT 'promax' COMMENT '调用源 rds/promax',
  params_json TEXT COMMENT '入参 JSON，支持 ${today} 等占位符',
  fields_json TEXT COMMENT '勾选字段 JSON',
  cron VARCHAR(64) NOT NULL COMMENT 'cron 表达式，Asia/Shanghai',
  target_table VARCHAR(64) NOT NULL COMMENT 'tusharedata 目标表',
  primary_keys VARCHAR(255) NOT NULL DEFAULT '' COMMENT '业务主键，逗号分隔，为空则按 source 全量替换',
  retry INT NOT NULL DEFAULT 0 COMMENT '失败重试次数',
  timeout INT NOT NULL DEFAULT 30 COMMENT '预留：单次执行超时秒数',
  watermark VARCHAR(32) NOT NULL DEFAULT '' COMMENT '增量水位线，最近成功的最大 trade_date',
  enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  last_status VARCHAR(16) NOT NULL DEFAULT '' COMMENT '最近一次运行状态',
  last_run_at DATETIME NULL COMMENT '最近一次运行开始时间',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='调度任务配置';

-- seq: 2
-- model: schedule_run
-- action: create
-- summary: 调度运行记录表，记录触发方式、状态、行数、错误信息与入参快照
CREATE TABLE IF NOT EXISTS schedule_run (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_id BIGINT UNSIGNED NOT NULL COMMENT '任务ID',
  trigger_type VARCHAR(16) NOT NULL DEFAULT 'cron' COMMENT 'cron/manual/retry',
  started_at DATETIME NOT NULL COMMENT '开始时间',
  finished_at DATETIME NULL COMMENT '结束时间',
  status VARCHAR(16) NOT NULL DEFAULT 'running' COMMENT 'running/success/failed',
  row_count INT NOT NULL DEFAULT 0 COMMENT '写入行数',
  message VARCHAR(500) NOT NULL DEFAULT '' COMMENT '结果或错误信息',
  params_snapshot TEXT COMMENT '替换占位符后的实际入参',
  PRIMARY KEY (id),
  KEY idx_job (job_id, id),
  KEY idx_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='调度运行记录';

-- seq: 3
-- model: schedule_job
-- action: create
-- summary: 预置任务：交易日历 trade_cal，每天 08:00 增量更新昨天起的日历
INSERT INTO schedule_job (name, doc_id, api_name, source, params_json, fields_json, cron, target_table, primary_keys, retry, timeout, enabled)
VALUES ('交易日历', '26', 'trade_cal', 'promax', '{"exchange":"SSE","start_date":"${yesterday}","end_date":"${today}"}', '["exchange","cal_date","is_open","pretrade_date"]', '0 8 * * *', 'trade_cal', 'exchange,cal_date', 1, 30, 1);

-- seq: 4
-- model: schedule_job
-- action: create
-- summary: 预置任务：股票列表 stock_basic，每周一 08:10
INSERT INTO schedule_job (name, doc_id, api_name, source, params_json, fields_json, cron, target_table, primary_keys, retry, timeout, enabled)
VALUES ('股票列表', '25', 'stock_basic', 'promax', '{"list_status":"L"}', '["ts_code","symbol","name","area","industry","market","exchange","list_date"]', '10 8 * * 1', 'stock_basic', 'ts_code', 1, 30, 1);

-- seq: 5
-- model: schedule_job
-- action: create
-- summary: 预置任务：A股日线 daily，工作日 18:00 拉取当天
INSERT INTO schedule_job (name, doc_id, api_name, source, params_json, fields_json, cron, target_table, primary_keys, retry, timeout, enabled)
VALUES ('A股日线', '27', 'daily', 'promax', '{"trade_date":"${trade_date}"}', '["ts_code","trade_date","open","high","low","close","pre_close","change","pct_chg","vol","amount"]', '0 18 * * 1-5', 'daily', 'ts_code,trade_date', 1, 30, 1);

-- seq: 6
-- model: schedule_job
-- action: create
-- summary: 预置任务：期货合约 fut_basic，每周一 08:20 按交易所逐个执行
INSERT INTO schedule_job (name, doc_id, api_name, source, params_json, fields_json, cron, target_table, primary_keys, retry, timeout, enabled)
VALUES ('期货合约', '135', 'fut_basic', 'promax', '{"exchange":"CFFEX,SHFE,DCE,CZCE,INE,GFEX","fut_type":"1"}', '["ts_code","symbol","exchange","name","fut_code","multiplier","trade_unit","per_unit","quote_unit","quote_unit_desc","d_mode_desc","list_date","delist_date","d_month","last_ddate"]', '20 8 * * 1', 'fut_basic', 'ts_code', 1, 30, 1);

-- seq: 7
-- model: schedule_job
-- action: create
-- summary: 预置任务：期货日线 fut_daily，每天 08:30 拉取前一自然日
INSERT INTO schedule_job (name, doc_id, api_name, source, params_json, fields_json, cron, target_table, primary_keys, retry, timeout, enabled)
VALUES ('期货日线', '138', 'fut_daily', 'promax', '{"trade_date":"${yesterday}"}', '["ts_code","trade_date","pre_close","pre_settle","open","high","low","close","settle","change1","change2","vol","amount","oi","oi_chg"]', '30 8 * * *', 'fut_daily', 'ts_code,trade_date', 1, 30, 1);
