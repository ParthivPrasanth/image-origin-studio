import type { ComparisonResponse, InspectionResponse, ModelKey } from "./types";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}

function formFor(file: File, models: readonly ModelKey[]) {
  const form = new FormData();
  form.append("file", file);
  models.forEach((model) => form.append("models", model));
  return form;
}

export async function analyze(
  file: File,
  models: readonly ModelKey[],
  options?: { token?: string; saveToHistory?: boolean },
): Promise<ComparisonResponse> {
  const form = formFor(file, models);
  if (options?.saveToHistory) form.append("save_to_history", "true");
  return parseResponse(
    await fetch("/api/analyze/compare", {
      method: "POST",
      body: form,
      headers: options?.token
        ? { Authorization: `Bearer ${options.token}` }
        : undefined,
    }),
  );
}

export async function inspect(
  file: File,
  models: readonly ModelKey[],
  signal: AbortSignal,
): Promise<InspectionResponse> {
  return parseResponse(
    await fetch("/api/inspect", {
      method: "POST",
      body: formFor(file, models),
      signal,
    }),
  );
}
