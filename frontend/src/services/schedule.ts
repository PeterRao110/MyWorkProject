export const CRON_PRESETS = [
  { label: "每天 08:00", value: "0 8 * * *" },
  { label: "每天 08:30", value: "30 8 * * *" },
  { label: "工作日 18:00", value: "0 18 * * 1-5" },
  { label: "每周一 08:10", value: "10 8 * * 1" },
  { label: "每周一 08:20", value: "20 8 * * 1" },
];

export type ScheduleJob = {
  id: number;
  name: string;
  docId: string;
  apiName: string;
  source: "rds" | "promax";
  params: Record<string, string>;
  fields: string[];
  cron: string;
  targetTable: string;
  primaryKeys: string[];
  retry: number;
  timeout: number;
  groupId: number | null;
  sortOrder: number;
  watermark: string;
  enabled: boolean;
  lastStatus: string;
  lastRunAt: string;
  nextRunAt: string;
};

export type ScheduleGroup = {
  id: number;
  name: string;
  cron: string;
  sortOrder: number;
  followPrevious: boolean;
  stopOnFailure: boolean;
  enabled: boolean;
  lastStatus: string;
  lastRunAt: string;
  nextRunAt: string;
  memberCount: number;
};

export type ScheduleRun = {
  id: number;
  jobId: number;
  jobName: string;
  apiName: string;
  source: string;
  fields: string[];
  params: Record<string, string>;
  groupRunId: number | null;
  triggerType: string;
  startedAt: string;
  finishedAt: string;
  status: string;
  rowCount: number;
  message: string;
};

export type ScheduleGroupRun = {
  id: number;
  groupId: number;
  triggerType: string;
  startedAt: string;
  finishedAt: string;
  status: string;
  message: string;
};

export type ScheduleRunState = {
  jobId: number;
  groupName: string;
  jobName: string;
  dateInterval: number;
  nextStartDate: string;
  nextEndDate: string;
  lastSuccessStart: string;
  lastSuccessEnd: string;
  durationMs: number | null;
  lastRowCount: number | null;
  lastSuccessAt: string;
  lastStatus: string;
};

export type ScheduleRunStateInput = {
  dateInterval: number;
  nextStartDate: string;
  nextEndDate: string;
  lastSuccessStart: string;
  lastSuccessEnd: string;
  durationMs: number | null;
  lastRowCount: number | null;
  lastSuccessAt: string;
};

export type ScheduleOverview = {
  leader: boolean;
  enabledJobs: number;
  enabledGroups: number;
  todaySuccess: number;
  todayFailed: number;
  running: number;
};

export type ScheduleJobInput = {
  name: string;
  docId: string;
  apiName: string;
  source: "rds" | "promax";
  params: Record<string, string>;
  fields: string[];
  cron: string;
  targetTable: string;
  primaryKeys: string[];
  retry: number;
  timeout: number;
  groupId: number | null;
  enabled: boolean;
};

export type ScheduleGroupInput = {
  name: string;
  cron: string;
  followPrevious: boolean;
  stopOnFailure: boolean;
  enabled: boolean;
};

export async function getScheduleOverview(): Promise<ScheduleOverview> {
  const response = await fetch("/api/schedule/overview");
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function listScheduleGroups(): Promise<ScheduleGroup[]> {
  const response = await fetch("/api/schedule/groups");
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function createScheduleGroup(input: ScheduleGroupInput): Promise<ScheduleGroup> {
  return send("/api/schedule/groups", "POST", input);
}

export async function updateScheduleGroup(id: number, input: ScheduleGroupInput): Promise<ScheduleGroup> {
  return send(`/api/schedule/groups/${id}`, "PUT", input);
}

export async function reorderScheduleGroups(ids: number[]): Promise<void> {
  await send("/api/schedule/groups/order", "PUT", { ids });
}

export async function toggleScheduleGroup(id: number, enabled: boolean): Promise<void> {
  await send(`/api/schedule/groups/${id}/toggle`, "POST", { enabled });
}

export async function deleteScheduleGroup(id: number): Promise<void> {
  await send(`/api/schedule/groups/${id}`, "DELETE");
}

export async function runScheduleGroup(id: number, chain = false): Promise<string> {
  const result = await send(`/api/schedule/groups/${id}/run`, "POST", { chain });
  return (result as { message?: string }).message || "已触发运行";
}

export async function listScheduleGroupRuns(groupId: number): Promise<ScheduleGroupRun[]> {
  const response = await fetch(`/api/schedule/groups/${groupId}/runs`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function listGroupRunCalls(groupRunId: number): Promise<ScheduleRun[]> {
  const response = await fetch(`/api/schedule/group-runs/${groupRunId}/calls`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function listScheduleJobs(): Promise<ScheduleJob[]> {
  const response = await fetch("/api/schedule/jobs");
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function createScheduleJob(input: ScheduleJobInput): Promise<ScheduleJob> {
  return send("/api/schedule/jobs", "POST", input);
}

export async function updateScheduleJob(id: number, input: ScheduleJobInput): Promise<ScheduleJob> {
  return send(`/api/schedule/jobs/${id}`, "PUT", input);
}

export async function reorderScheduleJobs(groupId: number, ids: number[]): Promise<void> {
  await send("/api/schedule/jobs/order", "PUT", { groupId, ids });
}

export async function toggleScheduleJob(id: number, enabled: boolean): Promise<void> {
  await send(`/api/schedule/jobs/${id}/toggle`, "POST", { enabled });
}

export async function deleteScheduleJob(id: number): Promise<void> {
  await send(`/api/schedule/jobs/${id}`, "DELETE");
}

export async function runScheduleJob(id: number): Promise<string> {
  const result = await send(`/api/schedule/jobs/${id}/run`, "POST");
  return (result as { message?: string }).message || "已触发运行";
}

export async function listScheduleRunStates(): Promise<ScheduleRunState[]> {
  const response = await fetch("/api/schedule/run-states");
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function updateScheduleRunState(jobId: number, input: ScheduleRunStateInput): Promise<ScheduleRunState> {
  return send(`/api/schedule/run-states/${jobId}`, "PUT", input);
}

export async function listScheduleRuns(jobId: number): Promise<ScheduleRun[]> {
  const response = await fetch(`/api/schedule/jobs/${jobId}/runs`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function retryScheduleRun(runId: number): Promise<string> {
  const result = await send(`/api/schedule/runs/${runId}/retry`, "POST");
  return (result as { message?: string }).message || "已触发重跑";
}

async function send(url: string, method: string, body?: unknown) {
  const response = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

async function readError(response: Response): Promise<string> {
  const payload = (await response.json().catch(() => ({}))) as {
    detail?: string | { msg?: string }[];
    message?: string;
  };
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg).filter(Boolean).join("；") || "请求失败";
  }
  return payload.detail || payload.message || "请求失败";
}
