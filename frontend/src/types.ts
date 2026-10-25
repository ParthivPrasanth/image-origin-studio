import type { CredentialResult } from "./c2pa";

export const MODEL_KEYS = ["v3_e2", "community_forensics"] as const;
export type ModelKey = (typeof MODEL_KEYS)[number];

export type InputMetadata = {
  sha256: string;
  width: number;
  height: number;
  image_format: string;
};

export type ModelSuccess = {
  model_key: ModelKey;
  status: "success";
  prediction: "fake" | "real";
  model_scores: { fake: number; real: number };
  model_id: string;
  model_revision: string;
  preprocessing_recipe: string;
  ai_score_threshold: number;
  elapsed_ms: number;
  analyzed_at: string;
};

export type ModelFailure = {
  model_key: ModelKey;
  status: "error";
  error: string;
  model_id: string;
  model_revision: string;
  preprocessing_recipe: string;
  ai_score_threshold: number;
  analyzed_at: string;
};

export type ModelResult = ModelSuccess | ModelFailure;
export type ComparisonResponse = {
  image_format: string;
  input: InputMetadata;
  analyzed_at: string;
  models: ModelResult[];
  history?: {
    status: "saved" | "not_saved";
    history_id?: string;
    expires_at?: string;
    reason?: string;
  } | null;
};
export type ComparisonResult = ComparisonResponse & {
  requestedModels: ModelKey[];
};

export type InspectionView = {
  key: string;
  title: string;
  width: number;
  height: number;
  recipe_id: string;
  description: string;
  preview_data_url: string;
  note?: string;
};
export type InspectionResponse = {
  input: InputMetadata;
  views: InspectionView[];
};

export type Item = {
  id: string;
  file: File;
  preview: string;
  state: "ready" | "processing" | "done" | "error";
  result?: ComparisonResult;
  runningModels?: ModelKey[];
  error?: string;
  credential?: CredentialResult;
};

export const MODEL_INFO: Record<ModelKey, { name: string; credit: string }> = {
  v3_e2: { name: "V3 E2", credit: "Owner-trained fusion model" },
  community_forensics: {
    name: "Community Forensics",
    credit: "External baseline · Thermostatic",
  },
};

export function modelName(key: ModelKey) {
  return MODEL_INFO[key].name;
}

export function resultFor(result: ComparisonResult, key: ModelKey) {
  return result.models.find((entry) => entry.model_key === key);
}

export function disagreement(result: ComparisonResult) {
  const e2 = resultFor(result, "v3_e2");
  const baseline = resultFor(result, "community_forensics");
  return e2?.status === "success" && baseline?.status === "success"
    ? e2.prediction !== baseline.prediction
    : null;
}
