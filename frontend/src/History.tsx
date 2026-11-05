import { useEffect, useRef, useState } from "react";
import C2paPanel from "./C2paPanel";
import {
  comparisonFromHistory,
  deleteHistoryAccount,
  deleteHistoryItem,
  getHistoryItem,
  getHistoryOriginal,
  listHistory,
  type HistoryItem,
  type HistoryPage,
  type HistoryQuota,
} from "./historyApi";
import { downloadReport, makeCaseReport, printReport } from "./report";
import type { CredentialResult } from "./c2pa";
import "./history.css";

type Props = {
  token: string | null;
  localAuthAvailable: boolean;
  cognitoAvailable: boolean;
  onSignIn?: () => void;
  onLocalSignIn?: (user: "alice" | "bob") => void;
  onOpenSavedItem?: (item: HistoryItem, original: File) => void;
};

type LoadedHistoryItem = {
  item: HistoryItem;
  original: File;
};

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function mimeType(item: HistoryItem, original: Blob) {
  if (original.type) return original.type;
  if (item.mime_type) return item.mime_type;
  const name = item.filename.toLowerCase();
  if (name.endsWith(".png")) return "image/png";
  if (name.endsWith(".webp")) return "image/webp";
  return "image/jpeg";
}

function isDeleting(item: HistoryItem) {
  return [item.status, item.deletion_state, item.deletion_status].includes(
    "deleting",
  );
}

function quotaText(quota: HistoryQuota) {
  const remainingItems = Math.max(0, quota.max_items - quota.used_items);
  const remainingBytes = Math.max(0, quota.max_bytes - quota.used_bytes);
  return `${quota.used_items} of ${quota.max_items} images · ${formatSize(quota.used_bytes)} of ${formatSize(quota.max_bytes)} used · ${remainingItems} image${remainingItems === 1 ? "" : "s"} and ${formatSize(remainingBytes)} remaining`;
}

export default function History({
  token,
  localAuthAvailable,
  cognitoAvailable,
  onSignIn,
  onLocalSignIn,
  onOpenSavedItem,
}: Props) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [quota, setQuota] = useState<HistoryQuota | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [loaded, setLoaded] = useState<LoadedHistoryItem | null>(null);
  const [credential, setCredential] = useState<CredentialResult>();
  const [previewUrl, setPreviewUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const [deletingAccount, setDeletingAccount] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const openRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!loaded) {
      setPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(loaded.original);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [loaded]);

  useEffect(() => {
    const controller = new AbortController();
    openRequest.current?.abort();
    openRequest.current = null;
    setItems([]);
    setNextCursor(null);
    setQuota(null);
    setSelectedId("");
    setLoaded(null);
    setCredential(undefined);
    setError("");
    if (!token) {
      setLoading(false);
      return () => controller.abort();
    }

    setLoading(true);
    listHistory(token, null, controller.signal)
      .then((page) => {
        setItems(page.items);
        setNextCursor(page.next_cursor);
        setQuota(page.quota);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason.message
              : "History could not be loaded.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, refreshKey]);

  useEffect(() => setMessage(""), [token]);

  async function openItem(summary: HistoryItem) {
    if (!token) return;
    openRequest.current?.abort();
    const controller = new AbortController();
    openRequest.current = controller;
    setSelectedId(summary.history_id);
    setLoaded(null);
    setCredential(undefined);
    setError("");
    setMessage("");
    setDetailLoading(true);
    try {
      const [item, blob] = await Promise.all([
        getHistoryItem(token, summary.history_id, controller.signal),
        getHistoryOriginal(token, summary.history_id, controller.signal),
      ]);
      if (controller.signal.aborted) return;
      const original = new File([blob], item.filename, {
        type: mimeType(item, blob),
        lastModified: new Date(item.created_at).valueOf() || Date.now(),
      });
      setLoaded({ item, original });
    } catch (reason) {
      if (!controller.signal.aborted)
        setError(
          reason instanceof Error &&
            reason.message === "History item unavailable."
            ? "This saved image is unavailable. It may have expired or been deleted. Refresh History to update the list."
            : reason instanceof Error
              ? reason.message
              : "This saved image is unavailable.",
        );
    } finally {
      if (!controller.signal.aborted) setDetailLoading(false);
    }
  }

  async function loadMore() {
    if (!token || !nextCursor || loadingMore) return;
    setLoadingMore(true);
    setError("");
    try {
      const page: HistoryPage = await listHistory(token, nextCursor);
      setItems((previous) => [...previous, ...page.items]);
      setNextCursor(page.next_cursor);
      setQuota(page.quota);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "More history could not be loaded.",
      );
    } finally {
      setLoadingMore(false);
    }
  }

  async function removeItem(item: HistoryItem) {
    if (!token || deletingId) return;
    if (!window.confirm(`Delete “${item.filename}” from your history?`)) return;
    setDeletingId(item.history_id);
    setError("");
    try {
      const deletion = await deleteHistoryItem(token, item.history_id);
      openRequest.current?.abort();
      setItems((previous) =>
        previous.filter((entry) => entry.history_id !== item.history_id),
      );
      if (selectedId === item.history_id) {
        setSelectedId("");
        setLoaded(null);
        setCredential(undefined);
      }
      setMessage(
        deletion.pending
          ? "The item is inaccessible. Original-file deletion is pending and will be retried."
          : "The saved image was deleted.",
      );
      setRefreshKey((value) => value + 1);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The image could not be deleted.",
      );
    } finally {
      setDeletingId("");
    }
  }

  async function removeAccountHistory() {
    if (!token || deletingAccount) return;
    if (
      !window.confirm(
        "Delete all saved images and analysis records for this account? This cannot be undone.",
      )
    )
      return;
    setDeletingAccount(true);
    setError("");
    try {
      const deletion = await deleteHistoryAccount(token);
      openRequest.current?.abort();
      setItems([]);
      setNextCursor(null);
      setQuota(null);
      setSelectedId("");
      setLoaded(null);
      setCredential(undefined);
      setMessage(
        deletion.pending > 0
          ? `${deletion.pending} file deletion${deletion.pending === 1 ? " is" : "s are"} pending retry. All saved items are inaccessible.`
          : "All saved images and analysis records were deleted.",
      );
      setRefreshKey((value) => value + 1);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Account history could not be deleted.",
      );
    } finally {
      setDeletingAccount(false);
    }
  }

  const result = loaded ? comparisonFromHistory(loaded.item) : null;
  const report =
    loaded && result
      ? makeCaseReport(loaded.item.filename, result, credential)
      : null;

  if (!token) {
    return (
      <section className="history-screen" aria-labelledby="history-title">
        <header className="history-heading">
          <p className="history-eyebrow">PRIVATE ACCOUNT DATA</p>
          <h1 id="history-title">History</h1>
          <p>
            {cognitoAvailable || localAuthAvailable
              ? "Sign in to view analyses you chose to save."
              : "History is available when sign-in is configured."}
          </p>
        </header>
        <div className="history-signin" role="status">
          <div className="history-signin-art" aria-hidden="true">
            <span className="history-art-sheet sheet-back" />
            <span className="history-art-sheet sheet-front">◌</span>
          </div>
          <div className="history-signin-copy">
            <p className="history-eyebrow">YOUR PRIVATE ARCHIVE</p>
            <h2>
              {cognitoAvailable || localAuthAvailable
                ? "A place for the analyses you keep."
                : "History is off"}
            </h2>
            <p>
              {cognitoAvailable || localAuthAvailable
                ? "History holds only analyses you choose to save before running them. Reopen the original image and its results, or delete them at any time."
                : "Sign-in is not configured. Analyze and Gallery remain available as a guest."}
            </p>
            {cognitoAvailable && onSignIn && (
              <button
                className="history-signin-button"
                type="button"
                onClick={onSignIn}
              >
                Sign in for History
              </button>
            )}
            {localAuthAvailable && onLocalSignIn && (
              <div
                className="history-signin-actions"
                aria-label="Local test sign-in"
              >
                <button
                  className="history-signin-button"
                  type="button"
                  onClick={() => onLocalSignIn("alice")}
                >
                  Continue as Alice
                </button>
                <button
                  className="history-signin-button secondary"
                  type="button"
                  onClick={() => onLocalSignIn("bob")}
                >
                  Continue as Bob
                </button>
              </div>
            )}
            <p className="history-guest-note">
              Analyze and Gallery are available without signing in.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="history-screen" aria-labelledby="history-title">
      <header className="history-heading">
        <p className="history-eyebrow">PRIVATE ACCOUNT DATA</p>
        <h1 id="history-title">History</h1>
        <p>
          Saved originals and result snapshots expire 30 days after saving.
          Opening an item does not extend its retention.
        </p>
      </header>

      {quota && (
        <div className="history-quota" aria-label="History storage quota">
          <span>{quotaText(quota)}</span>
          {(quota.used_items >= quota.max_items ||
            quota.used_bytes >= quota.max_bytes) && (
            <strong>
              History is full. Delete a saved image to make room, or analyze
              without saving.
            </strong>
          )}
          {quota.global_full && (
            <strong>New saves are paused while shared storage is full.</strong>
          )}
        </div>
      )}
      {error && (
        <p className="history-alert" role="alert">
          {error}
          {!loading && (
            <button
              className="history-link-button"
              type="button"
              onClick={() => setRefreshKey((value) => value + 1)}
            >
              Refresh History
            </button>
          )}
        </p>
      )}
      {message && (
        <p className="history-message" role="status">
          {message}
        </p>
      )}

      <div className="history-layout">
        <aside className="history-list-panel" aria-label="Saved analyses">
          <div className="history-list-heading">
            <h2>Saved analyses</h2>
            <button
              className="history-danger-link"
              type="button"
              disabled={deletingAccount || items.length === 0}
              onClick={removeAccountHistory}
            >
              {deletingAccount ? "Requesting deletion…" : "Delete all"}
            </button>
          </div>
          {loading ? (
            <p className="history-empty" role="status">
              Loading saved analyses…
            </p>
          ) : items.length === 0 ? (
            <div className="history-empty">
              <h3>No saved analyses</h3>
              <p>
                Choose “Save this analysis to my history” before analyzing an
                image.
              </p>
            </div>
          ) : (
            <ul className="history-items">
              {items.map((item) => (
                <li key={item.history_id}>
                  <button
                    className={`history-item-button${selectedId === item.history_id ? " selected" : ""}`}
                    type="button"
                    aria-current={
                      selectedId === item.history_id ? "true" : undefined
                    }
                    onClick={() => void openItem(item)}
                  >
                    <span className="history-item-name">{item.filename}</span>
                    <span className="history-item-meta">
                      {formatDate(item.created_at)} ·{" "}
                      {formatSize(item.byte_count)}
                    </span>
                    <span className="history-item-expiry">
                      Expires {formatDate(item.expires_at)}
                    </span>
                    {isDeleting(item) && (
                      <span className="history-pending">Deletion pending</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {nextCursor && (
            <button
              className="history-more"
              type="button"
              disabled={loadingMore}
              onClick={() => void loadMore()}
            >
              {loadingMore ? "Loading…" : "Load more"}
            </button>
          )}
        </aside>

        <div className="history-detail-panel" aria-live="polite">
          {detailLoading ? (
            <div className="history-empty" role="status">
              <p>Loading the saved result and original image…</p>
            </div>
          ) : loaded && result ? (
            <article className="history-detail">
              <div className="history-detail-heading">
                <div>
                  <p className="history-eyebrow">SAVED RESULT</p>
                  <h2>{loaded.item.filename}</h2>
                  <p>
                    Saved {formatDate(loaded.item.created_at)} · expires{" "}
                    {formatDate(loaded.item.expires_at)}
                  </p>
                </div>
                <button
                  className="history-delete-button"
                  type="button"
                  disabled={
                    deletingId === loaded.item.history_id ||
                    isDeleting(loaded.item)
                  }
                  onClick={() => void removeItem(loaded.item)}
                >
                  {deletingId === loaded.item.history_id
                    ? "Deleting…"
                    : "Delete"}
                </button>
              </div>

              {previewUrl && (
                <figure className="history-original">
                  <img
                    src={previewUrl}
                    alt={`Original saved image: ${loaded.item.filename}`}
                  />
                  <figcaption>
                    Unmodified original · {formatSize(loaded.item.byte_count)} ·
                    SHA-256 {loaded.item.original_sha256}
                  </figcaption>
                </figure>
              )}

              <section
                className="history-models"
                aria-labelledby="history-model-title"
              >
                <h3 id="history-model-title">Stored model results</h3>
                <p className="history-limitation">
                  These are the saved model suggestions from the original
                  analysis. They are not proof of image origin.
                </p>
                <div className="history-model-grid">
                  {result.requestedModels.map((key) => {
                    const model = result.models.find(
                      (entry) => entry.model_key === key,
                    );
                    const label =
                      key === "v3_e2" ? "V3 E2" : "Community Forensics";
                    return (
                      <section className="history-model" key={key}>
                        <h4>{label}</h4>
                        {!model ? (
                          <p>No stored result was returned for this model.</p>
                        ) : model.status === "error" ? (
                          <>
                            <p className="history-model-error">
                              Analysis error: {model.error}
                            </p>
                            <p>Model revision: {model.model_revision}</p>
                          </>
                        ) : (
                          <>
                            <p className="history-suggestion">
                              Suggestion:{" "}
                              <strong>
                                {model.prediction === "fake"
                                  ? "AI-generated"
                                  : "Real"}
                              </strong>
                            </p>
                            <p>
                              Model scores · AI-generated{" "}
                              {(model.model_scores.fake * 100).toFixed(1)}% ·
                              Real {(model.model_scores.real * 100).toFixed(1)}%
                            </p>
                            <p>Model revision: {model.model_revision}</p>
                            <p>
                              Decision cutoff:{" "}
                              {(model.ai_score_threshold * 100).toFixed(1)}%
                            </p>
                          </>
                        )}
                      </section>
                    );
                  })}
                </div>
              </section>

              <section
                className="history-report-actions"
                aria-label="Report actions"
              >
                <button
                  className="history-action"
                  type="button"
                  onClick={() => report && downloadReport(report)}
                >
                  Download JSON report
                </button>
                <button
                  className="history-action"
                  type="button"
                  onClick={() => report && printReport(report)}
                >
                  Print or save report as PDF
                </button>
                {onOpenSavedItem && (
                  <button
                    className="history-action"
                    type="button"
                    onClick={() =>
                      onOpenSavedItem(loaded.item, loaded.original)
                    }
                  >
                    Open in analysis workspace
                  </button>
                )}
              </section>

              <C2paPanel
                key={loaded.item.history_id}
                file={loaded.original}
                result={result}
                credential={credential}
                onResult={setCredential}
              />
            </article>
          ) : (
            <div className="history-empty history-prompt">
              <h2>Open a saved analysis</h2>
              <p>
                Select an item to retrieve its original image and stored result.
                Private image data is fetched only while viewing it.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
