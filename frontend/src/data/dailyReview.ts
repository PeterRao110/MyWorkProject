export type ExecResult = "pending" | "success" | "failure";
export type DayPhase = "planning" | "ready" | "reviewed";

export type PlanItem = {
  id: string;
  symbol: string;
  symbolName: string;
  price: number | null;
  trend: string;
  operationPlan: string;
  strategy: string;
  result: ExecResult;
  resultNote: string;
  nextPlan: string;
  reviewed: boolean;
};

export type DailyPlan = {
  date: string;
  items: PlanItem[];
};

export function phaseOf(plan: DailyPlan): DayPhase {
  if (plan.items.length > 0 && plan.items.every((item) => item.reviewed)) return "reviewed";
  if (plan.items.some((item) => item.reviewed)) return "ready";
  return "planning";
}
