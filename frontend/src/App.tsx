import { useEffect, useRef, useState } from "react";
import { analyze } from "./api";
import C2paPanel from "./C2paPanel";
import {
  beginCognitoLogin,
  clearCognitoSession,
  cognitoLogoutUrl,
  completeCognitoLogin,
  currentCognitoToken,
  type CognitoPublicConfig,
} from "./cognitoAuth";
import Gallery from "./Gallery";
import History from "./History";
import { galleryCases } from "./galleryData";
import InputInspector from "./InputInspector";
import { downloadReport, makeCaseReport, printReport } from "./report";
import {
  disagreement,
  MODEL_INFO,
  MODEL_KEYS,
  modelName,
  resultFor,
  type Item,
  type ModelKey,
} from "./types";

const MAX_FILES = 8;
const MAX_BYTES = 10 * 1024 * 1024;

function niceSize(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
function score(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function currentView() {
  if (window.location.hash === "#gallery") return "gallery";
  if (window.location.hash === "#history") return "history";
  return "analyze";
}

export default function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [selectedModels, setSelectedModels] = useState<ModelKey[]>([
    ...MODEL_KEYS,
  ]);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState("");
  const [view, setView] = useState<"analyze" | "gallery" | "history">(
    currentView,
  );
  const [token, setToken] = useState<string | null>(
    () =>
      currentCognitoToken() || sessionStorage.getItem("ios_local_test_token"),
  );
  const [authMode, setAuthMode] = useState<"cognito" | "local" | null>(() =>
    currentCognitoToken()
      ? "cognito"
      : sessionStorage.getItem("ios_local_test_token")
        ? "local"
        : null,
  );
  const [cognito, setCognito] = useState<CognitoPublicConfig | null>(null);
  const [testUser, setTestUser] = useState<string | null>(() =>
    sessionStorage.getItem("ios_local_test_user"),
  );
  const [localAuthAvailable, setLocalAuthAvailable] = useState(false);
  const [saveToHistory, setSaveToHistory] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const itemsRef = useRef(items);
  itemsRef.current = items;
  useEffect(
    () => () => {
      itemsRef.current.forEach((item) => URL.revokeObjectURL(item.preview));
    },
    [],
  );
  useEffect(() => {
    const updateView = () => setView(currentView());
    window.addEventListener("hashchange", updateView);
    return () => window.removeEventListener("hashchange", updateView);
  }, []);
  useEffect(() => {
    let active = true;
    fetch("/api/auth/capabilities")
      .then((response) => {
        if (!response.ok) throw new Error("Sign-in settings are unavailable.");
        return response.json() as Promise<{
          local_test_available?: boolean;
          cognito?: CognitoPublicConfig | null;
        }>;
      })
      .then(async (capabilities) => {
        if (!active) return;
        const hosted = capabilities.cognito ?? null;
        setCognito(hosted);
        setLocalAuthAvailable(capabilities.local_test_available === true);
        if (hosted) {
          sessionStorage.removeItem("ios_local_test_token");
          sessionStorage.removeItem("ios_local_test_user");
          setTestUser(null);
          try {
            const callbackToken = await completeCognitoLogin(hosted);
            if (!active) return;
            const accessToken = callbackToken || currentCognitoToken();
            setToken(accessToken);
            setAuthMode(accessToken ? "cognito" : null);
            if (callbackToken)
              setNotice("Signed in. You can now save analyses.");
          } catch (error) {
            if (!active) return;
            clearCognitoSession();
            setToken(null);
            setAuthMode(null);
            setNotice(
              error instanceof Error ? error.message : "Sign-in failed.",
            );
          }
        } else {
          clearCognitoSession();
          const localToken = capabilities.local_test_available
            ? sessionStorage.getItem("ios_local_test_token")
            : null;
          setToken(localToken);
          setAuthMode(localToken ? "local" : null);
        }
      })
      .catch(() => {
        if (!active) return;
        setLocalAuthAvailable(false);
        setCognito(null);
        setToken(null);
        setAuthMode(null);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (authMode !== "cognito" || !token) return;
    const timer = window.setInterval(() => {
      if (currentCognitoToken()) return;
      setToken(null);
      setAuthMode(null);
      setSaveToHistory(false);
      setNotice("Your sign-in expired. Sign in again to use History.");
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [authMode, token]);

  async function signIn(user: "alice" | "bob") {
    try {
      const response = await fetch("/api/auth/local-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ test_user: user }),
      });
      if (!response.ok) throw new Error("Local test sign-in failed.");
      const body = (await response.json()) as { access_token: string };
      sessionStorage.setItem("ios_local_test_token", body.access_token);
      sessionStorage.setItem("ios_local_test_user", user);
      setToken(body.access_token);
      setAuthMode("local");
      setTestUser(user);
      setNotice(`Signed in as local test user ${user}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Sign-in failed.");
    }
  }

  function signOut() {
    const hostedLogout =
      authMode === "cognito" && cognito ? cognitoLogoutUrl(cognito) : null;
    itemsRef.current.forEach((item) => URL.revokeObjectURL(item.preview));
    setItems([]);
    setSelectedId("");
    setSaveToHistory(false);
    sessionStorage.removeItem("ios_local_test_token");
    sessionStorage.removeItem("ios_local_test_user");
    clearCognitoSession();
    setToken(null);
    setTestUser(null);
    setAuthMode(null);
    setNotice("Signed out. Local image previews were cleared.");
    if (hostedLogout) window.location.assign(hostedLogout);
  }

  function toggleModel(key: ModelKey) {
    setSelectedModels((previous) => {
      if (previous.includes(key)) {
        return previous.length === 1
          ? previous
          : previous.filter((model) => model !== key);
      }
      return MODEL_KEYS.filter((model) => [...previous, key].includes(model));
    });
  }

  function addFiles(files: FileList | File[]) {
    const selected = Array.from(files);
    const room = MAX_FILES - items.length;
    if (room <= 0) {
      setNotice(`You can analyze up to ${MAX_FILES} images at once.`);
      return;
    }
    const accepted = selected.slice(0, room).filter((file) => {
      if (file.size > MAX_BYTES) {
        setNotice(`${file.name} exceeds the 10 MB limit.`);
        return false;
      }
      if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
        setNotice(`${file.name} must be JPEG, PNG, or WebP.`);
        return false;
      }
      return true;
    });
    if (selected.length > room) {
      setNotice(
        `Only the first ${room} files were added. The batch limit is ${MAX_FILES}.`,
      );
    } else if (accepted.length === selected.length) setNotice("");
    setItems((previous) => [
      ...previous,
      ...accepted.map((file) => ({
        id: crypto.randomUUID(),
        file,
        preview: URL.createObjectURL(file),
        state: "ready" as const,
      })),
    ]);
    setSelectedId((previous) => previous || "pending-selection");
    if (input.current) input.current.value = "";
  }

  function remove(id: string) {
    setItems((previous) => {
      const item = previous.find((candidate) => candidate.id === id);
      if (item) URL.revokeObjectURL(item.preview);
      return previous.filter((candidate) => candidate.id !== id);
    });
    if (selectedId === id) {
      setSelectedId(items.find((candidate) => candidate.id !== id)?.id ?? "");
    }
  }

  function clearBatch() {
    itemsRef.current.forEach((item) => URL.revokeObjectURL(item.preview));
    setItems([]);
    setSelectedId("");
    setNotice("");
  }

  async function run(
    ids: string[],
    models: ModelKey[] = selectedModels,
    merge = false,
  ) {
    if (busy) return;
    setBusy(true);
    const requested = [...models];
    for (const id of ids) {
      const item = itemsRef.current.find((candidate) => candidate.id === id);
      if (!item) continue;
      setItems((previous) =>
        previous.map((candidate) =>
          candidate.id === id
            ? {
                ...candidate,
                state: "processing",
                result: merge ? candidate.result : undefined,
                error: undefined,
                runningModels: requested,
              }
            : candidate,
        ),
      );
      try {
        const response = await analyze(item.file, requested, {
          token: token ?? undefined,
          saveToHistory: Boolean(token && saveToHistory && !merge),
        });
        setItems((previous) =>
          previous.map((candidate) => {
            if (candidate.id !== id) return candidate;
            const prior = merge ? candidate.result : undefined;
            if (prior && prior.input.sha256 !== response.input.sha256) {
              return {
                ...candidate,
                state: "error",
                error:
                  "The file bytes changed since the earlier analysis. Remove and add the image again.",
              };
            }
            const taggedModels = response.models.map((entry) => ({
              ...entry,
              analyzed_at: response.analyzed_at,
            }));
            const replaced = new Set(
              taggedModels.map((entry) => entry.model_key),
            );
            const mergedModels = prior
              ? [
                  ...prior.models.filter(
                    (entry) => !replaced.has(entry.model_key),
                  ),
                  ...taggedModels,
                ]
              : taggedModels;
            return {
              ...candidate,
              state: "done",
              error: undefined,
              runningModels: undefined,
              result: {
                image_format: response.image_format,
                input: response.input,
                analyzed_at: prior?.analyzed_at ?? response.analyzed_at,
                models: MODEL_KEYS.flatMap((key) =>
                  mergedModels.filter((entry) => entry.model_key === key),
                ),
                requestedModels: prior ? prior.requestedModels : requested,
                history: prior?.history ?? response.history,
              },
            };
          }),
        );
      } catch (error) {
        setItems((previous) =>
          previous.map((candidate) =>
            candidate.id === id
              ? {
                  ...candidate,
                  state: "error",
                  error:
                    error instanceof Error ? error.message : "Unknown error",
                }
              : candidate,
          ),
        );
      }
    }
    setBusy(false);
  }

  function exportCsv() {
    const modelColumns = MODEL_KEYS.flatMap((key) => [
      `${key}_status`,
      `${key}_prediction`,
      `${key}_fake_model_score`,
      `${key}_real_model_score`,
      `${key}_model_id`,
      `${key}_model_revision`,
      `${key}_ai_score_threshold`,
      `${key}_elapsed_ms`,
      `${key}_error`,
    ]);
    const rows = [
      [
        "file",
        "requested_models",
        "image_format",
        "disagreement",
        ...modelColumns,
      ],
      ...items
        .filter((item) => item.result)
        .map((item) => {
          const result = item.result!;
          const modelValues = MODEL_KEYS.flatMap((key) => {
            const entry = resultFor(result, key);
            if (!entry) return Array(9).fill("") as string[];
            if (entry.status === "error")
              return ["error", "", "", "", "", "", "", "", entry.error];
            return [
              "success",
              entry.prediction,
              String(entry.model_scores.fake),
              String(entry.model_scores.real),
              entry.model_id,
              entry.model_revision,
              String(entry.ai_score_threshold),
              String(entry.elapsed_ms),
              "",
            ];
          });
          const differs = disagreement(result);
          return [
            item.file.name,
            result.requestedModels.join(" + "),
            result.image_format,
            differs === null ? "" : String(differs),
            ...modelValues,
          ];
        }),
    ];
    // Spreadsheet programs may treat a filename or error beginning with =, +, - or @ as a formula.
    const csv = rows
      .map((row) =>
        row
          .map((value) => {
            const safe = /^\s*[=+\-@]/.test(value) ? `'${value}` : value;
            return `"${safe.replaceAll('"', '""')}"`;
          })
          .join(","),
      )
      .join("\r\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "image-origin-comparison.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  useEffect(() => {
    if (selectedId === "pending-selection" && items.length)
      setSelectedId(items[0].id);
    else if (selectedId && !items.some((item) => item.id === selectedId)) {
      setSelectedId(items[0]?.id ?? "");
    }
  }, [items, selectedId]);

  const pending = items.filter(
    (item) =>
      item.state === "ready" || (item.state === "error" && !item.result),
  );
  const completed = items.filter((item) => item.result);
  const selected = items.find((item) => item.id === selectedId);
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#analyze">
          Image Origin Studio
        </a>
        <nav className="topbar-nav" aria-label="Main navigation">
          <a
            href="#analyze"
            aria-current={view === "analyze" ? "page" : undefined}
          >
            Analyze
          </a>
          <a
            href="#gallery"
            aria-current={view === "gallery" ? "page" : undefined}
          >
            Gallery
          </a>
          <a
            href="#history"
            aria-current={view === "history" ? "page" : undefined}
          >
            History
          </a>
        </nav>
        <div className="test-account">
          {token ? (
            <>
              <span>
                {authMode === "cognito"
                  ? "Signed in"
                  : `Local test: ${testUser}`}
              </span>
              <button
                type="button"
                className="text-button"
                disabled={busy}
                onClick={signOut}
              >
                Sign out
              </button>
            </>
          ) : cognito ? (
            <button
              type="button"
              className="text-button"
              onClick={() =>
                beginCognitoLogin(cognito).catch(() =>
                  setNotice("Sign-in could not be started."),
                )
              }
            >
              Sign in for History
            </button>
          ) : localAuthAvailable ? (
            <>
              <span>Local test sign-in:</span>
              <button
                type="button"
                className="text-button"
                onClick={() => signIn("alice")}
              >
                Alice
              </button>
              <button
                type="button"
                className="text-button"
                onClick={() => signIn("bob")}
              >
                Bob
              </button>
            </>
          ) : null}
        </div>
      </header>
      <main>
        {notice && (
          <p className="notice app-notice" role="alert">
            {notice}
          </p>
        )}
        {view === "analyze" ? (
          <>
            <section className="intro">
              <p className="eyebrow">A WORKSPACE FOR IMAGE EVIDENCE</p>
              <h1>Look closer at what an image can tell you.</h1>
              <p>
                Compare independent model suggestions, inspect their inputs, and
                check for Content Credentials. None of these alone proves an
                image’s origin.
              </p>
            </section>
            <div className="analyze-layout">
              <section
                className="analyze-workspace"
                aria-label="Analyze images"
              >
                <div className="setup-heading">
                  <p className="eyebrow">GET STARTED</p>
                  <h2>Set up an analysis</h2>
                  <p>Choose images and models, then review each result.</p>
                </div>
                <div className="upload-strip">
                  <div
                    className="dropzone compact-dropzone"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault();
                      addFiles(event.dataTransfer.files);
                    }}
                  >
                    <div className="step-title">
                      <span className="step-number">01</span>
                      <strong>Add images</strong>
                    </div>
                    <span>
                      JPEG, PNG, or WebP · up to 10 MB each · 8 per batch
                    </span>
                    <button
                      type="button"
                      className="primary"
                      onClick={() => input.current?.click()}
                    >
                      Choose images
                    </button>
                    <input
                      ref={input}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      multiple
                      hidden
                      onChange={(event) =>
                        event.target.files && addFiles(event.target.files)
                      }
                    />
                  </div>
                  <fieldset className="model-selector" disabled={busy}>
                    <legend>
                      <span className="step-number">02</span> Choose models
                    </legend>
                    {MODEL_KEYS.map((key) => (
                      <label className="model-choice" key={key}>
                        <input
                          type="checkbox"
                          checked={selectedModels.includes(key)}
                          onChange={() => toggleModel(key)}
                          aria-describedby={`${key}-credit`}
                        />
                        <span>
                          <strong>{modelName(key)}</strong>
                          <small id={`${key}-credit`}>
                            {MODEL_INFO[key].credit}
                          </small>
                        </span>
                      </label>
                    ))}
                    <p className="selector-note">
                      Both are selected by default. Changing this does not
                      relabel earlier results.
                    </p>
                    {token && (
                      <label className="save-choice">
                        <input
                          type="checkbox"
                          checked={saveToHistory}
                          onChange={(event) =>
                            setSaveToHistory(event.target.checked)
                          }
                        />
                        <span>
                          <strong>Save this analysis to my history</strong>
                          <small>
                            Off by default. Applies to each file in the next
                            analysis batch. Keeps each unmodified original,
                            including embedded metadata, and its result for 30
                            days.
                          </small>
                        </span>
                      </label>
                    )}
                    {!token && (
                      <p className="save-hint">
                        Saving is optional after sign-in. Guest analyses stay
                        out of History.
                      </p>
                    )}
                  </fieldset>
                </div>
                <p className="privacy-note">
                  {cognito ? (
                    <>
                      <strong>Privacy:</strong> Images are sent to this service
                      for analysis. Guest and unsaved analyses are not added to
                      History. Signed-in users can choose to save the unmodified
                      original and result for 30 days.
                    </>
                  ) : (
                    <>
                      <strong>Local privacy:</strong> Images are processed by
                      the API on this PC. Guest and unsaved analyses are not
                      added to History. Local test users can explicitly opt in
                      to saving.
                    </>
                  )}
                </p>
              </section>

              {items.length === 0 ? (
                <section className="empty-state compact-empty">
                  <span className="empty-state-symbol" aria-hidden="true">
                    ◌
                  </span>
                  <p className="eyebrow">YOUR WORKSPACE</p>
                  <h2>Your images and results will appear here.</h2>
                  <p>
                    Add an image to begin. You can select up to eight images,
                    then review one result at a time.
                  </p>
                </section>
              ) : (
                <section
                  className="review-workspace"
                  aria-label="Image results"
                >
                  <div className="image-queue">
                    <div className="queue-heading">
                      <h2>
                        <span className="step-number">03</span> Image queue
                      </h2>
                      <span>
                        {items.length} of {MAX_FILES}
                      </span>
                    </div>
                    <div className="batch-actions">
                      {pending.length > 0 && (
                        <button
                          className="primary small"
                          disabled={busy}
                          onClick={() => run(pending.map((item) => item.id))}
                        >
                          {busy ? "Processing…" : `Analyze ${pending.length}`}
                        </button>
                      )}
                      {completed.length > 0 && (
                        <button className="text-button" onClick={exportCsv}>
                          Export CSV
                        </button>
                      )}
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={clearBatch}
                      >
                        Clear batch
                      </button>
                    </div>
                    <ul className="result-list">
                      {items.map((item) => {
                        const outcomes = item.result?.requestedModels
                          .map((key) => {
                            const entry = resultFor(item.result!, key);
                            return entry?.status === "success"
                              ? `${modelName(key)}: ${entry.prediction === "fake" ? "AI-generated" : "Real"}`
                              : entry?.status === "error"
                                ? `${modelName(key)}: error`
                                : "";
                          })
                          .filter(Boolean)
                          .join(" · ");
                        return (
                          <li
                            key={item.id}
                            className={`queue-item ${item.id === selected?.id ? "selected" : ""}`}
                          >
                            <button
                              type="button"
                              className="queue-select"
                              aria-current={
                                item.id === selected?.id ? "true" : undefined
                              }
                              onClick={() => setSelectedId(item.id)}
                            >
                              <img src={item.preview} alt="" />
                              <span className="queue-copy">
                                <strong title={item.file.name}>
                                  {item.file.name}
                                </strong>
                                <small>
                                  {item.state === "processing"
                                    ? "Analyzing…"
                                    : item.state === "ready"
                                      ? "Ready to analyze"
                                      : item.state === "error"
                                        ? "Request error"
                                        : outcomes || "Analysis complete"}
                                </small>
                              </span>
                            </button>
                            <button
                              className="remove"
                              title="Remove image"
                              aria-label={`Remove ${item.file.name}`}
                              disabled={busy}
                              onClick={() => remove(item.id)}
                            >
                              ×
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                  {selected && (
                    <article
                      className="selected-detail"
                      aria-labelledby="selected-title"
                    >
                      <div className="detail-heading">
                        <div>
                          <p className="eyebrow">SELECTED IMAGE</p>
                          <h2 id="selected-title" title={selected.file.name}>
                            {selected.file.name}
                          </h2>
                          <p className="file-meta">
                            {niceSize(selected.file.size)} ·{" "}
                            {selected.file.type.split("/")[1]?.toUpperCase()}
                          </p>
                          {selected.result && (
                            <p className="file-meta">
                              API input: {selected.result.input.width} ×{" "}
                              {selected.result.input.height} px ·{" "}
                              {selected.result.image_format} · analyzed{" "}
                              {new Date(
                                selected.result.analyzed_at,
                              ).toLocaleString()}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="result-stage">
                        <div className="selected-preview">
                          <img
                            src={selected.preview}
                            alt={`Preview of ${selected.file.name}`}
                          />
                          <div className="preview-caption">
                            <span>Original upload</span>
                            <span>{niceSize(selected.file.size)}</span>
                          </div>
                        </div>
                        <div className="result-content">
                          {selected.state === "processing" && (
                            <p className="state processing" role="status">
                              Analyzing with{" "}
                              {selected.runningModels
                                ?.map(modelName)
                                .join(" and ")}
                              …
                            </p>
                          )}
                          {selected.state === "error" && (
                            <p className="state error" role="alert">
                              {selected.error}{" "}
                              <button
                                className="text-button"
                                disabled={busy}
                                onClick={() =>
                                  run(
                                    [selected.id],
                                    selected.runningModels ?? selectedModels,
                                    Boolean(selected.result),
                                  )
                                }
                              >
                                Retry request
                              </button>
                            </p>
                          )}
                          {selected.result ? (
                            <div className="analysis">
                              {selected.result.history?.status === "saved" && (
                                <p className="save-status" role="status">
                                  Saved to private history until{" "}
                                  {new Date(
                                    selected.result.history.expires_at!,
                                  ).toLocaleDateString()}
                                  . <a href="#history">Open History</a>
                                </p>
                              )}
                              {selected.result.history?.status ===
                                "not_saved" && (
                                <p className="save-status error" role="alert">
                                  Analysis complete but not saved:{" "}
                                  {selected.result.history.reason}
                                </p>
                              )}
                              {disagreement(selected.result) === true && (
                                <p className="disagreement" role="status">
                                  The models disagree on this image. Their
                                  suggestions and scores are independent.
                                </p>
                              )}
                              <div className="model-rows">
                                {selected.result.requestedModels.map((key) => {
                                  const entry = resultFor(
                                    selected.result!,
                                    key,
                                  );
                                  return (
                                    <section
                                      className="model-row"
                                      key={key}
                                      aria-label={`${modelName(key)} result`}
                                    >
                                      <div>
                                        <h3>{modelName(key)}</h3>
                                        <p className="model-credit">
                                          {MODEL_INFO[key].credit}
                                        </p>
                                      </div>
                                      {entry?.status === "success" ? (
                                        <div
                                          className={`model-suggestion ${entry.prediction}`}
                                        >
                                          <span>Suggests</span>
                                          <strong>
                                            {entry.prediction === "fake"
                                              ? "AI-generated"
                                              : "Real"}
                                          </strong>
                                          <small>
                                            AI model score{" "}
                                            {score(entry.model_scores.fake)} ·
                                            cutoff{" "}
                                            {score(entry.ai_score_threshold)}
                                          </small>
                                          <span
                                            className="score-track"
                                            aria-hidden="true"
                                          >
                                            <span
                                              className="score-fill"
                                              style={{
                                                width: `${entry.model_scores.fake * 100}%`,
                                              }}
                                            />
                                            <span
                                              className="score-cutoff"
                                              style={{
                                                left: `${entry.ai_score_threshold * 100}%`,
                                              }}
                                            />
                                          </span>
                                        </div>
                                      ) : (
                                        <div className="model-suggestion error">
                                          <strong>
                                            {entry?.status === "error"
                                              ? "Could not analyze"
                                              : "No result returned"}
                                          </strong>
                                          {entry?.status === "error" && (
                                            <button
                                              className="text-button"
                                              disabled={busy}
                                              onClick={() =>
                                                run([selected.id], [key], true)
                                              }
                                            >
                                              Retry {modelName(key)}
                                            </button>
                                          )}
                                        </div>
                                      )}
                                      {entry?.status === "success" && (
                                        <details className="technical-details">
                                          <summary>Technical details</summary>
                                          <p>
                                            Real model score:{" "}
                                            {score(entry.model_scores.real)}
                                          </p>
                                          <p>
                                            AI-generated model score:{" "}
                                            {score(entry.model_scores.fake)}
                                          </p>
                                          <p>
                                            Cutoff:{" "}
                                            {score(entry.ai_score_threshold)} ·{" "}
                                            {entry.elapsed_ms.toFixed(0)} ms
                                          </p>
                                          <p>Model: {entry.model_id}</p>
                                          <p>
                                            Revision: {entry.model_revision}
                                          </p>
                                          <p>
                                            Preprocessing:{" "}
                                            {entry.preprocessing_recipe}
                                          </p>
                                        </details>
                                      )}
                                      {entry?.status === "error" && (
                                        <>
                                          <p
                                            className="model-error"
                                            role="alert"
                                          >
                                            {entry.error}
                                          </p>
                                          <details className="technical-details">
                                            <summary>
                                              Model and decision details
                                            </summary>
                                            <p>Model: {entry.model_id}</p>
                                            <p>
                                              Revision: {entry.model_revision}
                                            </p>
                                            <p>
                                              Preprocessing:{" "}
                                              {entry.preprocessing_recipe}
                                            </p>
                                            <p>
                                              AI flagging cutoff:{" "}
                                              {score(entry.ai_score_threshold)}
                                            </p>
                                          </details>
                                        </>
                                      )}
                                    </section>
                                  );
                                })}
                              </div>
                            </div>
                          ) : (
                            selected.state === "ready" && (
                              <p className="state ready">
                                Ready to analyze. Use the batch action beside
                                the image list.
                              </p>
                            )
                          )}
                          <C2paPanel
                            key={selected.id}
                            file={selected.file}
                            result={selected.result}
                            credential={selected.credential}
                            onResult={(credential) =>
                              setItems((previous) =>
                                previous.map((candidate) =>
                                  candidate.id === selected.id
                                    ? { ...candidate, credential }
                                    : candidate,
                                ),
                              )
                            }
                          />
                          {selected.result && (
                            <details className="secondary-actions">
                              <summary>Inspect inputs or export report</summary>
                              <InputInspector
                                key={selected.result.models
                                  .map(
                                    (entry) =>
                                      `${entry.model_key}:${entry.analyzed_at}:${entry.status}`,
                                  )
                                  .join("|")}
                                file={selected.file}
                                result={selected.result}
                                id={selected.id}
                              />
                              <div className="report-actions">
                                <button
                                  className="text-button"
                                  type="button"
                                  onClick={() =>
                                    downloadReport(
                                      makeCaseReport(
                                        selected.file.name,
                                        selected.result!,
                                        selected.credential,
                                      ),
                                    )
                                  }
                                >
                                  Download JSON report
                                </button>
                                <button
                                  className="text-button"
                                  type="button"
                                  onClick={() =>
                                    printReport(
                                      makeCaseReport(
                                        selected.file.name,
                                        selected.result!,
                                        selected.credential,
                                      ),
                                    )
                                  }
                                >
                                  Print or save PDF
                                </button>
                                <button
                                  className="text-button"
                                  disabled={busy}
                                  onClick={() => run([selected.id])}
                                >
                                  Analyze again
                                </button>
                              </div>
                            </details>
                          )}
                        </div>
                      </div>
                    </article>
                  )}
                </section>
              )}
            </div>
            <details className="about">
              <summary>How to read this comparison</summary>
              <h2>Two scores are not a verdict.</h2>
              <p>
                V3 E2 is the owner’s trained fusion model using FFT features and
                a frozen pretrained MobileNetV3 backbone. Community Forensics is
                an external baseline by Thermostatic. Each model uses its own
                preprocessing and decision cutoff. Their scores are not
                calibrated to each other, so a larger number from one model does
                not mean stronger evidence than a smaller number from the other.
              </p>
              <p>
                Both models can be wrong, including when they agree.
                Disagreement is useful to inspect, but neither result proves how
                an image was made. Community Forensics is credited at{" "}
                <a
                  href="https://huggingface.co/Thermostatic/community-forensics-frontier-detector-2026-08"
                  target="_blank"
                  rel="noreferrer"
                >
                  its model page
                </a>
                .
              </p>
            </details>
          </>
        ) : view === "gallery" ? (
          <Gallery cases={galleryCases} />
        ) : (
          <History
            token={token}
            localAuthAvailable={localAuthAvailable}
            cognitoAvailable={Boolean(cognito)}
            onSignIn={
              cognito
                ? () =>
                    beginCognitoLogin(cognito).catch(() =>
                      setNotice("Sign-in could not be started."),
                    )
                : undefined
            }
            onLocalSignIn={signIn}
          />
        )}
      </main>
      <footer>
        Image Origin Studio · {cognito ? "Hosted release" : "Local release"} ·
        Model suggestions are not proof of origin
      </footer>
    </div>
  );
}
