import { useState } from "react";
import type { CredentialResult } from "./c2pa";
import { modelName, type ComparisonResult } from "./types";

type Props = {
  file: File;
  result?: ComparisonResult;
  credential?: CredentialResult;
  onResult: (credential: CredentialResult) => void;
};

const STATUS_TEXT: Record<CredentialResult["status"], string> = {
  trusted: "Credential validated; signer trusted by the bundled C2PA list.",
  valid: "Credential validated; signer trust is unresolved.",
  invalid: "Credential validation failed. Its origin claims are not verified.",
  absent: "No Content Credential found. The image’s origin remains unknown.",
  unsupported: "This file format is unsupported by the credential validator.",
  error: "Unable to validate Content Credentials for this file.",
};

export default function C2paPanel({
  file,
  result,
  credential,
  onResult,
}: Props) {
  const [checking, setChecking] = useState(false);
  const [localError, setLocalError] = useState("");
  const conflicts =
    credential?.aiGeneratedClaim &&
    (credential.status === "valid" || credential.status === "trusted")
      ? (result?.models ?? [])
          .filter(
            (model) =>
              model.status === "success" && model.prediction === "real",
          )
          .map((model) => modelName(model.model_key))
      : [];

  async function check() {
    setChecking(true);
    setLocalError("");
    try {
      const { inspectCredentials } = await import("./c2pa");
      onResult(await inspectCredentials(file));
    } catch (error) {
      setLocalError(
        error instanceof Error
          ? error.message
          : "Credential check could not start.",
      );
    } finally {
      setChecking(false);
    }
  }

  return (
    <section className="credential-panel" aria-label="Content Credentials">
      <div className="credential-heading">
        <div>
          <h4>Content Credentials</h4>
          <p>Signed creation history from the original file</p>
        </div>
        <button
          className="text-button"
          type="button"
          disabled={checking}
          onClick={check}
        >
          {checking
            ? "Checking…"
            : credential
              ? "Check again"
              : "Check credentials"}
        </button>
      </div>
      {!credential && !checking && !localError && (
        <p className="credential-note">
          Open this separately from model analysis. The file stays in this
          browser while the validator checks its original bytes.
        </p>
      )}
      {checking && <p role="status">Validating the original file…</p>}
      {localError && (
        <p className="credential-error" role="alert">
          {localError}
        </p>
      )}
      {credential && (
        <div className="credential-result" aria-live="polite">
          <p className={`credential-status ${credential.status}`}>
            {STATUS_TEXT[credential.status]}
          </p>
          {(credential.status === "valid" ||
            credential.status === "trusted") && (
            <>
              <p>
                <strong>Creation claim:</strong>{" "}
                {credential.aiGeneratedClaim
                  ? credential.aiClaimSource === "parent"
                    ? "AI-generated origin declared in an earlier validated credential."
                    : "AI-generated media declared in the active credential."
                  : "No AI-generation declaration found in the validated creation chain."}
              </p>
              {conflicts.length > 0 && (
                <p className="credential-conflict" role="status">
                  Credential and model disagree: the credential declares AI
                  generation; {conflicts.join(" and ")} suggests real. Both
                  results are shown as reported.
                </p>
              )}
            </>
          )}
          <details className="credential-details">
            <summary>Validation details</summary>
            {credential.aiClaimSource === "parent" &&
              credential.aiClaimSigner && (
                <p>
                  <strong>Origin claim signer:</strong>{" "}
                  {credential.aiClaimSigner}
                </p>
              )}
            {(credential.signer || credential.issuer) && (
              <p>
                <strong>Signer:</strong> {credential.signer ?? "Not named"}
                {credential.issuer && ` · Issuer: ${credential.issuer}`}
              </p>
            )}
            {credential.actions.length > 0 && (
              <p>
                <strong>Recorded actions:</strong>{" "}
                {credential.actions.join(", ")}
              </p>
            )}
            {credential.validationProblems.length > 0 && (
              <p>{credential.validationProblems.join(", ")}</p>
            )}
            <p className="credential-meta">
              SDK {credential.sdkVersion} · Trust list:{" "}
              {credential.trustList === "bundled-c2pa"
                ? "bundled C2PA list"
                : "unavailable"}
            </p>
          </details>
        </div>
      )}
      <p className="credential-help">
        A validated credential verifies a signed claim about this file.{" "}
        <a
          href="https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html"
          target="_blank"
          rel="noreferrer"
        >
          How Content Credentials work
        </a>
      </p>
    </section>
  );
}
