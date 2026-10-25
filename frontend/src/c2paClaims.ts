const AI_SOURCE_TYPE =
  "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia";

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function actionsIn(manifest: Record<string, unknown>): {
  names: string[];
  declaresAi: boolean;
} {
  const names: string[] = [];
  let declaresAi = false;
  if (!Array.isArray(manifest.assertions)) return { names, declaresAi };
  for (const entry of manifest.assertions) {
    const assertion = record(entry);
    if (!optionalString(assertion?.label)?.startsWith("c2pa.actions")) continue;
    const data = record(assertion?.data);
    if (!Array.isArray(data?.actions)) continue;
    for (const value of data.actions) {
      const action = record(value);
      const name = optionalString(action?.action);
      if (name && names.length < 12) names.push(name);
      if (action?.digitalSourceType === AI_SOURCE_TYPE) declaresAi = true;
    }
  }
  return { names, declaresAi };
}

function validatedParentLabels(manifest: Record<string, unknown>): string[] {
  if (!Array.isArray(manifest.ingredients)) return [];
  return manifest.ingredients.flatMap((value) => {
    const ingredient = record(value);
    if (ingredient?.relationship !== "parentOf") return [];
    const label = optionalString(ingredient.active_manifest);
    const validation = record(
      record(ingredient.validation_results)?.activeManifest,
    );
    const successes = Array.isArray(validation?.success)
      ? validation.success.map((item) => optionalString(record(item)?.code))
      : [];
    const failures = validation?.failure;
    return label &&
      Array.isArray(failures) &&
      failures.length === 0 &&
      successes.includes("claimSignature.validated") &&
      successes.includes("assertion.dataHash.match")
      ? [label]
      : [];
  });
}

export function verifiedClaimDetails(store: Record<string, unknown>) {
  const manifests = record(store.manifests);
  const activeLabel = optionalString(store.active_manifest);
  const active = activeLabel ? record(manifests?.[activeLabel]) : null;
  const signature = record(active?.signature_info);
  const activeActions = active
    ? actionsIn(active)
    : { names: [], declaresAi: false };

  let aiClaimSource: "active" | "parent" | undefined;
  let aiClaimSigner: string | undefined;
  if (activeActions.declaresAi) {
    aiClaimSource = "active";
    aiClaimSigner = optionalString(signature?.common_name);
  } else if (active && activeLabel && manifests) {
    const visited = new Set([activeLabel]);
    const queue = validatedParentLabels(active);
    while (queue.length && visited.size < 32) {
      const label = queue.shift();
      if (!label || visited.has(label)) continue;
      visited.add(label);
      const parent = record(manifests[label]);
      if (!parent) continue;
      if (actionsIn(parent).declaresAi) {
        aiClaimSource = "parent";
        aiClaimSigner = optionalString(
          record(parent.signature_info)?.common_name,
        );
        break;
      }
      queue.push(...validatedParentLabels(parent));
    }
  }

  return {
    aiGeneratedClaim: Boolean(aiClaimSource),
    aiClaimSource,
    aiClaimSigner,
    actions: activeActions.names,
    signer: optionalString(signature?.common_name),
    issuer: optionalString(signature?.issuer),
  };
}
