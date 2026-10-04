-- version: 1.0.0
-- title: 初始模型

-- seq: 1
-- model: schema_model_change
-- action: create
-- summary: 按版本号记录每一次模型变更，包含模型名、动作、说明和语句
CREATE TABLE IF NOT EXISTS schema_model_change (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  version VARCHAR(32) NOT NULL COMMENT '版本号',
  seq INT UNSIGNED NOT NULL COMMENT '同一版本内的执行序号',
  model_name VARCHAR(64) NOT NULL COMMENT '模型名',
  action VARCHAR(16) NOT NULL COMMENT 'create、alter、drop',
  summary VARCHAR(500) NOT NULL COMMENT '变更说明',
  ddl MEDIUMTEXT NOT NULL COMMENT '变更语句',
  applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '写入时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_version_seq (version, seq),
  KEY idx_version (version),
  KEY idx_model (model_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据库模型变更记录';
