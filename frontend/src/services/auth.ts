export type AuthStatus = {
  configured: boolean;
  authenticated: boolean;
};

let sessionKnown = false;
let signedIn = false;

export function markSignedIn() {
  sessionKnown = true;
  signedIn = true;
}

export function markSignedOut() {
  sessionKnown = true;
  signedIn = false;
}

export async function getAuthStatus(): Promise<AuthStatus> {
  const response = await fetch("/api/auth/status");
  if (!response.ok) throw new Error("无法读取登录状态");
  return response.json();
}

export async function hasSession(): Promise<boolean> {
  if (sessionKnown) return signedIn;
  const status = await getAuthStatus();
  signedIn = status.authenticated;
  sessionKnown = true;
  return signedIn;
}

export async function setupPassword(password: string, confirm: string): Promise<void> {
  const response = await fetch("/api/auth/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password, confirm }),
  });
  if (!response.ok) throw new Error(await readDetail(response, "设置密码失败"));
  markSignedIn();
}

export async function login(password: string): Promise<void> {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!response.ok) throw new Error(await readDetail(response, "登录失败"));
  markSignedIn();
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
  markSignedOut();
}

async function readDetail(response: Response, fallback: string) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    return fallback;
  }
  return fallback;
}
