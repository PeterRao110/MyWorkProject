-- version: 1.5.0
-- title: 每日计划复盘

-- seq: 1
-- model: daily_plan
-- action: create
-- summary: 每个执行日期一份计划
CREATE TABLE IF NOT EXISTS daily_plan (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  trade_date DATE NOT NULL COMMENT '执行日期',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日执行计划';

-- seq: 2
-- model: daily_plan_item
-- action: create
-- summary: 计划条目，包含品种、价格、趋势、操作计划、操作策略和按品种保存的复盘
CREATE TABLE IF NOT EXISTS daily_plan_item (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  plan_id BIGINT UNSIGNED NOT NULL COMMENT '所属计划',
  sort_order INT NOT NULL DEFAULT 0 COMMENT '同一天内的顺序',
  symbol VARCHAR(32) NOT NULL COMMENT '品种代码',
  symbol_name VARCHAR(64) NOT NULL COMMENT '品种名称',
  price DECIMAL(18, 4) NULL COMMENT '加入计划时的当前价格',
  trend VARCHAR(500) NOT NULL DEFAULT '' COMMENT '品种当前趋势',
  operation_plan VARCHAR(2000) NOT NULL COMMENT '操作计划',
  strategy VARCHAR(2000) NOT NULL DEFAULT '' COMMENT '操作策略',
  result VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT '执行结果：pending未执行 success成功 failure失败',
  result_note VARCHAR(2000) NOT NULL DEFAULT '' COMMENT '执行结果描述',
  next_plan VARCHAR(2000) NOT NULL DEFAULT '' COMMENT '下次计划',
  reviewed TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已保存复盘',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_plan_sort (plan_id, sort_order),
  CONSTRAINT fk_daily_plan_item_plan FOREIGN KEY (plan_id) REFERENCES daily_plan (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日计划条目';
