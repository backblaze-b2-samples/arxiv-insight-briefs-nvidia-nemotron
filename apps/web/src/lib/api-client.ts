import type {
  BriefDetail,
  BriefRequest,
  BriefSummary,
  HealthStatus,
  PresignedLink,
} from "@arxiv-insight-briefs/shared";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Typed API error with HTTP status code for caller-side branching. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isRetryable(): boolean {
    return [408, 429, 500, 502, 503, 504].includes(this.status);
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    // Network failure (offline, DNS, CORS, etc.)
    throw new ApiError("Network error — check your connection", 0);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail || `API error: ${res.status}`, res.status);
  }
  return res.json();
}

export async function getHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health");
}

export async function submitBriefing(payload: BriefRequest) {
  return apiFetch<{ brief_id: string; status: string }>("/briefings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listBriefings(limit = 100): Promise<BriefSummary[]> {
  return apiFetch<BriefSummary[]>(`/briefings?limit=${limit}`);
}

export async function getBriefing(id: string): Promise<BriefDetail> {
  return apiFetch<BriefDetail>(`/briefings/${encodeURIComponent(id)}`);
}

export async function cancelBriefing(id: string) {
  return apiFetch<void>(
    `/briefings/${encodeURIComponent(id)}?mode=cancel`,
    { method: "DELETE" },
  );
}

export async function clearBriefing(id: string) {
  return apiFetch<void>(
    `/briefings/${encodeURIComponent(id)}?mode=clear`,
    { method: "DELETE" },
  );
}

export async function presignPaper(
  arxivId: string,
  filename?: string,
): Promise<PresignedLink> {
  const qs = filename ? `?filename=${encodeURIComponent(filename)}` : "";
  return apiFetch<PresignedLink>(
    `/papers/${encodeURIComponent(arxivId)}/presign${qs}`,
  );
}
