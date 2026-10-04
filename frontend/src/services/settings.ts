export type DatabaseSettings = {
  host: string;
  port: string;
  database: string;
  user: string;
  passwordSet: boolean;
};

export type DatabaseSettingsInput = {
  host: string;
  port: string;
  database: string;
  user: string;
  password: string;
};

type SettingsResult = {
  ok: boolean;
  message: string;
};

export async function getDatabaseSettings(): Promise<DatabaseSettings> {
  const response = await fetch("/api/settings/database");
  if (!response.ok) throw new Error("读取数据库配置失败");
  return response.json();
}

export async function saveDatabaseSettings(input: DatabaseSettingsInput): Promise<SettingsResult> {
  return postDatabase("/api/settings/database", input);
}

export async function testDatabaseSettings(input: DatabaseSettingsInput): Promise<SettingsResult> {
  return postDatabase("/api/settings/database/test", input);
}

export type AkshareSettings = {
  enabled: boolean;
  baseUrl: string;
  timeout: string;
  retry: string;
};

export type TushareApiSettings = {
  baseUrl: string;
  timeout: string;
  retry: string;
  tokenSet: boolean;
};

export type SourceSettings = {
  akshare: AkshareSettings;
  rds: TushareApiSettings;
  promax: TushareApiSettings;
};

export async function getSourceSettings(): Promise<SourceSettings> {
  const response = await fetch("/api/settings/sources");
  if (!response.ok) throw new Error("读取接口配置失败");
  return response.json();
}

export async function saveAkshareSettings(input: AkshareSettings): Promise<SettingsResult> {
  return postJson("/api/settings/akshare", {
    enabled: input.enabled,
    baseUrl: input.baseUrl,
    timeout: Number(input.timeout),
    retry: Number(input.retry),
  });
}

export async function saveTushareSettings(input: {
  rds: { token: string; baseUrl: string; timeout: string; retry: string };
  promax: { token: string; baseUrl: string; timeout: string; retry: string };
}): Promise<SettingsResult> {
  return postJson("/api/settings/tushare", {
    rds: apiBody(input.rds),
    promax: apiBody(input.promax),
  });
}

function apiBody(input: { token: string; baseUrl: string; timeout: string; retry: string }) {
  return {
    token: input.token,
    baseUrl: input.baseUrl,
    timeout: Number(input.timeout),
    retry: Number(input.retry),
  };
}

async function postJson(url: string, body: unknown): Promise<SettingsResult> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = (await response.json().catch(() => ({}))) as {
    message?: string;
    detail?: string | { msg?: string }[];
  };
  if (!response.ok) {
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg).filter(Boolean).join("；")
      : payload.detail;
    throw new Error(detail || payload.message || "请求失败");
  }
  return { ok: true, message: payload.message || "完成" };
}

async function postDatabase(url: string, input: DatabaseSettingsInput): Promise<SettingsResult> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      host: input.host,
      port: Number(input.port),
      database: input.database,
      user: input.user,
      password: input.password,
    }),
  });
  const payload = (await response.json().catch(() => ({}))) as {
    message?: string;
    detail?: string | { msg?: string }[];
  };
  if (!response.ok) {
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg).filter(Boolean).join("；")
      : payload.detail;
    throw new Error(detail || payload.message || "请求失败");
  }
  return { ok: true, message: payload.message || "完成" };
}
