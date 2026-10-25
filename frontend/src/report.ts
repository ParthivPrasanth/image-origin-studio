import {
  disagreement,
  modelName,
  resultFor,
  type ComparisonResult,
  type ModelKey,
  type ModelResult,
} from "./types";
import type { CredentialResult } from "./c2pa";

export const REPORT_SCHEMA = "image-origin-case-report/v2";
export const LIMITATION =
  "Model suggestions are not proof of image origin or calibrated probabilities for arbitrary uploads. Each model has its own preprocessing and decision threshold. No combined verdict is produced.";

export type CaseReport = {
  schema: typeof REPORT_SCHEMA;
  filename: string;
  input: ComparisonResult["input"];
  analyzed_at: string;
  requested_models: ModelKey[];
  models: ModelResult[];
  disagreement: boolean | null;
  content_credentials: CredentialResult | null;
  limitation: string;
};

export function makeCaseReport(
  filename: string,
  result: ComparisonResult,
  credential?: CredentialResult,
): CaseReport {
  return {
    schema: REPORT_SCHEMA,
    filename,
    input: { ...result.input },
    analyzed_at: result.analyzed_at,
    requested_models: [...result.requestedModels],
    models: result.requestedModels.flatMap((key) => {
      const entry = resultFor(result, key);
      return entry ? [{ ...entry }] : [];
    }),
    disagreement: disagreement(result),
    content_credentials: credential
      ? {
          ...credential,
          actions: [...credential.actions],
          validationProblems: [...credential.validationProblems],
        }
      : null,
    limitation: LIMITATION,
  };
}

export function downloadReport(report: CaseReport) {
  const blob = new Blob([JSON.stringify(report, null, 2) + "\n"], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `image-origin-case-${report.input.sha256.slice(0, 12)}.json`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function addText(
  parent: HTMLElement,
  tag: string,
  content: string,
  className?: string,
) {
  const element = parent.ownerDocument.createElement(tag);
  element.textContent = content;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

export function printReport(report: CaseReport) {
  document.querySelector(".report-overlay")?.remove();
  const overlay = addText(document.body, "div", "", "report-overlay");
  const content = addText(overlay, "article", "", "print-report");
  content.setAttribute("role", "dialog");
  content.setAttribute("aria-modal", "true");
  content.setAttribute("aria-label", "Case report preview");
  const toolbar = addText(content, "div", "", "report-toolbar");
  const close = addText(toolbar, "button", "Close report");
  const print = addText(toolbar, "button", "Print or save as PDF");
  const previousFocus = document.activeElement as HTMLElement | null;
  const app = document.querySelector(".app-shell");
  app?.setAttribute("inert", "");
  const closeReport = () => {
    overlay.remove();
    app?.removeAttribute("inert");
    document.removeEventListener("keydown", onKeyDown);
    previousFocus?.focus();
  };
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") closeReport();
  };
  close.addEventListener("click", closeReport);
  print.addEventListener("click", () => window.print());
  document.addEventListener("keydown", onKeyDown);
  close.focus();
  addText(content, "p", "IMAGE ORIGIN STUDIO · LOCAL CASE REPORT", "eyebrow");
  addText(content, "h1", "Image inspection case report");
  addText(content, "p", `Analysis timestamp: ${report.analyzed_at}`, "muted");
  const meta = addText(content, "section", "", "meta");
  addText(meta, "p", `Filename: ${report.filename}`);
  addText(
    meta,
    "p",
    `Format: ${report.input.image_format} · ${report.input.width} × ${report.input.height} pixels`,
  );
  addText(meta, "p", `Original file SHA-256: ${report.input.sha256}`, "hash");
  addText(
    meta,
    "p",
    `Requested models: ${report.requested_models.map(modelName).join(", ")}`,
  );
  addText(content, "h2", "Separate model suggestions");
  report.requested_models.forEach((key) => {
    const entry = report.models.find((model) => model.model_key === key);
    const section = addText(content, "section", "", "model");
    addText(section, "h3", modelName(key));
    if (!entry) {
      addText(section, "p", "No result was returned for this model.");
      return;
    }
    addText(
      section,
      "p",
      `Status: ${entry.status} · analyzed: ${entry.analyzed_at}`,
    );
    addText(
      section,
      "p",
      `Model: ${entry.model_id} · revision: ${entry.model_revision}`,
    );
    addText(
      section,
      "p",
      `Preprocessing recipe: ${entry.preprocessing_recipe}`,
    );
    addText(
      section,
      "p",
      `AI flagging cutoff: ${(entry.ai_score_threshold * 100).toFixed(1)}%`,
    );
    if (entry.status === "error") {
      addText(section, "p", `Error: ${entry.error}`);
    } else {
      addText(
        section,
        "p",
        `Suggestion: ${entry.prediction === "fake" ? "AI-generated" : "Real"}`,
      );
      addText(
        section,
        "p",
        `AI model score: ${(entry.model_scores.fake * 100).toFixed(1)}% · Real model score: ${(entry.model_scores.real * 100).toFixed(1)}%`,
      );
      addText(section, "p", `Elapsed: ${entry.elapsed_ms.toFixed(1)} ms`);
    }
  });
  addText(
    content,
    "p",
    report.disagreement === true
      ? "The two successful models disagree."
      : report.disagreement === false
        ? "The two successful models agree; agreement does not establish origin."
        : "Disagreement cannot be determined from these results.",
  );
  addText(content, "h2", "Content Credentials");
  const credential = report.content_credentials;
  if (!credential) {
    addText(
      content,
      "p",
      "Content Credentials were not checked for this case.",
    );
  } else {
    const credentialSection = addText(content, "section", "", "model");
    addText(
      credentialSection,
      "p",
      `Validation: ${credential.status} · SDK ${credential.sdkVersion} · ${credential.method}`,
    );
    addText(
      credentialSection,
      "p",
      `Trust list: ${credential.trustList === "bundled-c2pa" ? "bundled C2PA list" : "unavailable"}`,
    );
    if (credential.status === "valid" || credential.status === "trusted") {
      addText(
        credentialSection,
        "p",
        credential.aiGeneratedClaim
          ? credential.aiClaimSource === "parent"
            ? "An earlier validated credential declares AI-generated origin."
            : "Active credential declares AI-generated media."
          : "No AI-generation declaration found in the validated creation chain.",
      );
      if (credential.aiClaimSource === "parent" && credential.aiClaimSigner)
        addText(
          credentialSection,
          "p",
          `Origin claim signer: ${credential.aiClaimSigner}`,
        );
      if (credential.signer || credential.issuer)
        addText(
          credentialSection,
          "p",
          `Signer: ${credential.signer ?? "Not named"} · Issuer: ${credential.issuer ?? "Not named"}`,
        );
      if (credential.actions.length)
        addText(
          credentialSection,
          "p",
          `Recorded actions: ${credential.actions.join(", ")}`,
        );
      const conflicts = credential.aiGeneratedClaim
        ? report.models
            .filter(
              (model) =>
                model.status === "success" && model.prediction === "real",
            )
            .map((model) => modelName(model.model_key))
        : [];
      if (conflicts.length)
        addText(
          credentialSection,
          "p",
          `Credential declares AI generation; ${conflicts.join(" and ")} suggests real.`,
        );
    }
    if (credential.validationProblems.length)
      addText(
        credentialSection,
        "p",
        `Validation details: ${credential.validationProblems.join(", ")}`,
      );
  }
  addText(content, "h2", "How to interpret this case");
  addText(content, "p", report.limitation, "limit");
  addText(
    content,
    "p",
    "The original image is omitted. Match this report to the exact file using the SHA-256 hash.",
    "muted",
  );
}
