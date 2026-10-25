import type {
  ComparisonResult,
  InputMetadata,
  ModelFailure,
  ModelKey,
  ModelSuccess,
} from "./types";

export type StoredModelResult =
  | (Omit<ModelSuccess, "analyzed_at"> & { analyzed_at?: string })
  | (Omit<ModelFailure, "analyzed_at"> & { analyzed_at?: string });

export type HistoryResultSnapshot = {
  image_format: string;
  input: InputMetadata;
  analyzed_at: string;
  models: StoredModelResult[];
};

export type HistoryItem = {
  history_id: string;
  filename: string;
  created_at: string;
  expires_at: string;
  byte_count: number;
  original_sha256: string;
  requested_models: ModelKey[];
  result: HistoryResultSnapshot;
  mime_type?: string;
  status?: string;
  deletion_state?: string;
  deletion_status?: string;
};

export type HistoryQuota = {
  used_items: number;
  max_items: number;
  used_bytes: number;
  max_bytes: number;
  global_full?: boolean;
};

export type HistoryPage = {
  items: HistoryItem[];
  next_cursor: string | null;
  quota: HistoryQuota;
};

export type HistoryAccountDeleteResponse = {
  deleted: number;
  pending: number;
  complete: boolean;
};

async function errorMessage(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return `History request failed (${response.status}).`;
}

async function expectJson<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json() as Promise<T>;
}

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

export async function listHistory(
  token: string,
  cursor?: string | null,
  signal?: AbortSignal,
): Promise<HistoryPage> {
  const query = cursor ? `?${new URLSearchParams({ cursor })}` : "";
  return expectJson(
    await fetch(`/api/history${query}`, {
      headers: authHeaders(token),
      cache: "no-store",
      signal,
    }),
  );
}

export async function getHistoryItem(
  token: string,
  historyId: string,
  signal?: AbortSignal,
): Promise<HistoryItem> {
  return expectJson(
    await fetch(`/api/history/${encodeURIComponent(historyId)}`, {
      headers: authHeaders(token),
      cache: "no-store",
      signal,
    }),
  );
}

export async function getHistoryOriginal(
  token: string,
  historyId: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await fetch(
    `/api/history/${encodeURIComponent(historyId)}/original`,
    {
      headers: authHeaders(token),
      cache: "no-store",
      signal,
    },
  );
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.blob();
}

export async function deleteHistoryItem(
  token: string,
  historyId: string,
): Promise<{ deleted: boolean; pending: boolean }> {
  const response = await fetch(
    `/api/history/${encodeURIComponent(historyId)}`,
    { method: "DELETE", headers: authHeaders(token), cache: "no-store" },
  );
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json() as Promise<{ deleted: boolean; pending: boolean }>;
}

export async function deleteHistoryAccount(
  token: string,
): Promise<HistoryAccountDeleteResponse> {
  const response = await fetch("/api/history/account", {
    method: "DELETE",
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json() as Promise<HistoryAccountDeleteResponse>;
}

export function comparisonFromHistory(item: HistoryItem): ComparisonResult {
  const timestamp = item.result.analyzed_at || item.created_at;
  return {
    image_format: item.result.image_format,
    input: item.result.input,
    analyzed_at: timestamp,
    models: item.result.models.map((model) => ({
      ...model,
      analyzed_at: model.analyzed_at || timestamp,
    })) as ComparisonResult["models"],
    requestedModels: [...item.requested_models],
  };
}
