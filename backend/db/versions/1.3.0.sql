-- version: 1.3.0
-- title: 交易日历改由期货日历承接

-- seq: 1
-- model: schedule_job
-- action: alter
-- summary: 期货交易日历同步增加 pretrade_date，下次运行从接口写入该字段
UPDATE schedule_job
SET fields_json = JSON_ARRAY_APPEND(fields_json, '$', 'pretrade_date')
WHERE api_name = 'fut_trade_cal'
  AND target_table = 'fut_trade_cal'
  AND JSON_CONTAINS(fields_json, '"pretrade_date"') = 0;

-- seq: 2
-- model: schedule_run
-- action: drop
-- summary: 删除 trade_cal 任务的运行记录，避免任务重建数据表
DELETE schedule_run
FROM schedule_run
INNER JOIN schedule_job ON schedule_job.id = schedule_run.job_id
WHERE schedule_job.api_name = 'trade_cal'
  AND schedule_job.target_table = 'trade_cal';

-- seq: 3
-- model: schedule_job
-- action: drop
-- summary: 删除 trade_cal 定时任务，同步改走 fut_trade_cal
DELETE FROM schedule_job
WHERE api_name = 'trade_cal'
  AND target_table = 'trade_cal';

-- seq: 4
-- model: trade_cal
-- action: drop
-- summary: 删除 tusharedata.trade_cal，交易日改从 fut_trade_cal 读取
DROP TABLE IF EXISTS tusharedata.trade_cal;
