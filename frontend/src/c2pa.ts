import { createC2pa, Context, Reader } from "@contentauth/c2pa-web";
import wasmSrc from "@contentauth/c2pa-web/resources/c2pa.wasm?url";
import { verifiedClaimDetails } from "./c2paClaims";

export const C2PA_SDK_VERSION = "0.15.4";
export const C2PA_METHOD = "Official c2pa-web SDK on original file bytes";
export const TRUST_LIST_URL = "/c2pa/anchors.pem";

export type CredentialStatus =
  | "trusted"
  | "valid"
  | "invalid"
  | "absent"
  | "unsupported"
  | "error";

export type CredentialResult = {
  status: CredentialStatus;
  aiGeneratedClaim: boolean;
  aiClaimSource?: "active" | "parent";
  aiClaimSigner?: string;
  signer?: string;
  issuer?: string;
  actions: string[];
  validationState?: string;
  validationProblems: string[];
  trustList: "bundled-c2pa" | "unavailable";
  checkedAt: string;
  method: typeof C2PA_METHOD;
  sdkVersion: typeof C2PA_SDK_VERSION;
};

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function validationProblems(store: Record<string, unknown>): string[] {
  const results = record(store.validation_results);
  const failure = record(results?.activeManifest)?.failure;
  if (!Array.isArray(failure)) return [];
  return failure
    .map((item) => record(item))
    .map((item) => optionalString(item?.code))
    .filter((code): code is string => Boolean(code))
    .slice(0, 8);
}

async function bundledTrustAnchors(): Promise<string | undefined> {
  try {
    const response = await fetch(TRUST_LIST_URL);
    if (!response.ok) return undefined;
    const pem = await response.text();
    return pem.includes("-----BEGIN CERTIFICATE-----") ? pem : undefined;
  } catch {
    return undefined;
  }
}

export async function inspectCredentials(
  file: File,
): Promise<CredentialResult> {
  const base = {
    checkedAt: new Date().toISOString(),
    method: C2PA_METHOD as typeof C2PA_METHOD,
    sdkVersion: C2PA_SDK_VERSION as typeof C2PA_SDK_VERSION,
    aiGeneratedClaim: false,
    actions: [] as string[],
    validationProblems: [] as string[],
  };
  const anchors = await bundledTrustAnchors();
  const trustList = anchors ? "bundled-c2pa" : "unavailable";
  let c2pa: Awaited<ReturnType<typeof createC2pa>> | undefined;
  let reader: Reader | null = null;
  try {
    c2pa = await createC2pa({ wasmSrc });
    const context = new Context({
      verify: { verifyTrust: true, verifyAfterReading: true },
      ...(anchors ? { trust: { trustAnchors: anchors } } : {}),
    });
    reader = await Reader.fromBlob(c2pa, file.type, file, context);
    if (!reader) return { ...base, status: "absent", trustList };
    const store = record(await reader.manifestStore());
    if (!store) return { ...base, status: "error", trustList };
    const state = optionalString(store.validation_state);
    const problems = validationProblems(store);
    const valid = state === "Trusted" || state === "Valid";
    const details = valid ? verifiedClaimDetails(store) : null;
    return {
      ...base,
      status:
        state === "Trusted" && anchors
          ? "trusted"
          : state === "Trusted" || state === "Valid"
            ? "valid"
            : state === "Invalid"
              ? "invalid"
              : "error",
      trustList,
      validationState: state,
      validationProblems: problems,
      ...(details ?? {}),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const unsupported =
      /unsupported (format|type|mime)|format .*not supported/i.test(message);
    return {
      ...base,
      status: unsupported ? "unsupported" : "error",
      trustList,
      validationProblems: [message.slice(0, 240)],
    };
  } finally {
    if (reader) await reader.free().catch(() => undefined);
    c2pa?.dispose();
  }
}
