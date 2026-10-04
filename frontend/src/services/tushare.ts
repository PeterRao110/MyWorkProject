export type ApiParam = {
  name: string;
  type: string;
  required: boolean;
  desc: string;
};

export type ApiField = {
  name: string;
  type: string;
  desc: string;
  shown: boolean;
};

export type ApiSchema = {
  docId: string;
  title: string;
  apiName: string;
  desc: string;
  params: ApiParam[];
  fields: ApiField[];
};

export type TushareTable = {
  fields: string[];
  items: Array<Array<string | number | null>>;
  message: string;
};

export async function getTushareSchema(docId: string): Promise<ApiSchema> {
  const response = await fetch(`/api/tushare/docs/${docId}`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function queryTushare(input: {
  source: "rds" | "promax";
  apiName: string;
  params: Record<string, string>;
  fields: string[];
}): Promise<TushareTable> {
  const response = await fetch("/api/tushare/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

async function readError(response: Response): Promise<string> {
  const payload = (await response.json().catch(() => ({}))) as { detail?: string; message?: string };
  return payload.detail || payload.message || "请求失败";
}
