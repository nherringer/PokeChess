const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("pokechess_token");
}

function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("pokechess_token", token);
}

async function refreshToken(): Promise<string | null> {
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (data.access_token) {
      setToken(data.access_token);
      if (data.user_id && typeof window !== "undefined") {
        localStorage.setItem("pokechess_user_id", data.user_id);
      }
      return data.access_token;
    }
    return null;
  } catch {
    return null;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  retried = false
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers,
  });

  if (res.status === 401 && !retried) {
    const newToken = await refreshToken();
    if (newToken) {
      return apiFetch<T>(path, options, true);
    }
    throw new ApiError("Unauthorized", "UNAUTHORIZED", 401);
  }

  if (!res.ok) {
    let errorMessage = "An error occurred";
    let errorCode = "UNKNOWN";
    try {
      const errorData = await res.json();
      // AppError uses { error: machine code, detail: human message }; prefer detail.
      errorCode = errorData.code ?? errorData.error ?? errorCode;
      const detail = errorData.detail;
      if (typeof detail === "string") {
        errorMessage = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        errorMessage = detail[0]?.msg ?? errorMessage;
      } else if (typeof errorData.error === "string" && errorData.error !== errorCode) {
        errorMessage = errorData.error;
      }
    } catch {
      // ignore parse errors
    }
    throw new ApiError(errorMessage, errorCode, res.status);
  }

  // Handle empty responses (e.g. 204 No Content)
  const contentType = res.headers.get("content-type");
  if (!contentType || !contentType.includes("application/json")) {
    return {} as T;
  }

  return res.json() as Promise<T>;
}
