import { AuthSession, User, Workspace } from "@/types";

const ACCESS_KEY = "supportai_access_token";
const REFRESH_KEY = "supportai_refresh_token";
const USER_KEY = "supportai_user";
const WORKSPACES_KEY = "supportai_workspaces";
const ACTIVE_WS_KEY = "supportai_active_workspace_id";

export function saveSession(session: AuthSession): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACCESS_KEY, session.access_token);
  localStorage.setItem(REFRESH_KEY, session.refresh_token);
  localStorage.setItem(USER_KEY, JSON.stringify(session.user));
  localStorage.setItem(WORKSPACES_KEY, JSON.stringify(session.workspaces || []));
  const currentWs = localStorage.getItem(ACTIVE_WS_KEY);
  const validCurrent = session.workspaces?.some(
    (w) => String(w.id) === currentWs
  );
  if (!validCurrent && session.workspaces?.length > 0) {
    localStorage.setItem(ACTIVE_WS_KEY, String(session.workspaces[0].id));
  }
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(WORKSPACES_KEY);
  localStorage.removeItem(ACTIVE_WS_KEY);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function saveStoredUser(user: User, workspaces?: Workspace[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  if (workspaces) {
    localStorage.setItem(WORKSPACES_KEY, JSON.stringify(workspaces));
  }
}

export function getStoredWorkspaces(): Workspace[] {
  if (typeof window === "undefined") return [];
  const raw = localStorage.getItem(WORKSPACES_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as Workspace[];
  } catch {
    return [];
  }
}

export function getActiveWorkspaceId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(ACTIVE_WS_KEY);
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function setActiveWorkspaceId(workspaceId: number): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACTIVE_WS_KEY, String(workspaceId));
}
