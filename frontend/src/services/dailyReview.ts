import type { DailyPlan, ExecResult, PlanItem } from "@/data/dailyReview";

export type PlanItemInput = {
  symbol: string;
  symbolName: string;
  price: number | null;
  trend: string;
  operationPlan: string;
  strategy: string;
};

export type ReviewInput = {
  result: ExecResult;
  resultNote: string;
  nextPlan: string;
};

export async function listDailyPlans(): Promise<DailyPlan[]> {
  const response = await fetch("/api/daily-plans");
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function createDailyPlanItem(date: string, input: PlanItemInput): Promise<DailyPlan> {
  return send(`/api/daily-plans/${date}/items`, "POST", input);
}

export async function moveDailyPlanItem(date: string, item: PlanItem, direction: -1 | 1): Promise<DailyPlan> {
  return send(`/api/daily-plans/${date}/items/${item.id}/move`, "PUT", { direction });
}

export async function removeDailyPlanItem(date: string, item: PlanItem): Promise<DailyPlan> {
  return send(`/api/daily-plans/${date}/items/${item.id}`, "DELETE");
}

export async function saveDailyPlanReview(date: string, item: PlanItem, review: ReviewInput): Promise<DailyPlan> {
  return send(`/api/daily-plans/${date}/items/${item.id}/review`, "PUT", review);
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
  };
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg).filter(Boolean).join("；") || "请求失败";
  }
  return payload.detail || "请求失败";
}
