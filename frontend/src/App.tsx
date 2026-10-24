import { useEffect, useRef, useState } from "react";

const MODEL_KEYS = ["v3_e2", "community_forensics"] as const;
type ModelKey = (typeof MODEL_KEYS)[number];
type ModelSuccess = {
  model_key: ModelKey;
  status: "success";
  prediction: "fake" | "real";
  model_scores: { fake: number; real: number };
  model_id: string;
  model_revision: string;
  ai_score_threshold: number;
  elapsed_ms: number;
};
type ModelFailure = { model_key: ModelKey; status: "error"; error: string };
type ModelResult = ModelSuccess | ModelFailure;
type ComparisonResponse = { image_format: string; models: ModelResult[] };
type ComparisonResult = ComparisonResponse & { requestedModels: ModelKey[] };
type Item = {
  id: string;
  file: File;
  preview: string;
  state: "ready" | "processing" | "done" | "error";
  result?: ComparisonResult;
  runningModels?: ModelKey[];
  error?: string;
};
const MAX_FILES = 8;
const MAX_BYTES = 10 * 1024 * 1024;
const MODEL_INFO: Record<ModelKey, { name: string; credit: string }> = {
  v3_e2: { name: "V3 E2", credit: "Owner-trained fusion model" },
  community_forensics: {
    name: "Community Forensics",
    credit: "External baseline · Thermostatic",
  },
};

function niceSize(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
function score(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}
function modelName(key: ModelKey) {
  return MODEL_INFO[key].name;
}
function resultFor(result: ComparisonResult, key: ModelKey) {
  return result.models.find((entry) => entry.model_key === key);
}
function disagreement(result: ComparisonResult) {
  const e2 = resultFor(result, "v3_e2");
  const baseline = resultFor(result, "community_forensics");
  return e2?.status === "success" && baseline?.status === "success"
    ? e2.prediction !== baseline.prediction
    : null;
}
async function analyze(
  file: File,
  models: readonly ModelKey[],
): Promise<ComparisonResponse> {
  const form = new FormData();
  form.append("file", file);
  models.forEach((model) => form.append("models", model));
  const response = await fetch("/api/analyze/compare", {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  }
  return response.json();
}

export default function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [selectedModels, setSelectedModels] = useState<ModelKey[]>([
    ...MODEL_KEYS,
  ]);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const itemsRef = useRef(items);
  itemsRef.current = items;
  useEffect(
    () => () => {
      itemsRef.current.forEach((item) => URL.revokeObjectURL(item.preview));
    },
    [],
  );

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
    if (input.current) input.current.value = "";
  }

  function remove(id: string) {
    setItems((previous) => {
      const item = previous.find((candidate) => candidate.id === id);
      if (item) URL.revokeObjectURL(item.preview);
      return previous.filter((candidate) => candidate.id !== id);
    });
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
        const response = await analyze(item.file, requested);
        setItems((previous) =>
          previous.map((candidate) => {
            if (candidate.id !== id) return candidate;
            const prior = merge ? candidate.result : undefined;
            const replaced = new Set(
              response.models.map((entry) => entry.model_key),
            );
            const mergedModels = prior
              ? [
                  ...prior.models.filter(
                    (entry) => !replaced.has(entry.model_key),
                  ),
                  ...response.models,
                ]
              : response.models;
            return {
              ...candidate,
              state: "done",
              error: undefined,
              runningModels: undefined,
              result: {
                image_format: response.image_format,
                models: MODEL_KEYS.flatMap((key) =>
                  mergedModels.filter((entry) => entry.model_key === key),
                ),
                requestedModels: prior ? prior.requestedModels : requested,
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

  const pending = items.filter(
    (item) =>
      item.state === "ready" || (item.state === "error" && !item.result),
  );
  const completed = items.filter((item) => item.result);
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            ◈
          </span>
          <span>Image Origin Studio</span>
        </div>
        <span className="topbar-tag">Research model demo</span>
      </header>
      <main>
        <section className="intro">
          <div className="eyebrow">IMAGE ANALYSIS / LOCAL DEMO</div>
          <h1>Compare what two models see.</h1>
          <p>
            Run your trained V3 E2 model, an external Community Forensics
            baseline, or both on the same images. Each result is an experimental
            model suggestion, never proof of an image’s origin.
          </p>
        </section>
        <div className="workspace">
          <section className="upload-panel" aria-labelledby="upload-title">
            <div className="section-heading">
              <span className="step">01</span>
              <div>
                <h2 id="upload-title">Choose images and models</h2>
                <p>
                  JPEG, PNG, or WebP · up to 10 MB each · {MAX_FILES} per batch
                </p>
              </div>
            </div>
            <div
              className="dropzone"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                addFiles(event.dataTransfer.files);
              }}
            >
              <div className="upload-symbol" aria-hidden="true">
                ↑
              </div>
              <strong>Drop images here</strong>
              <span>or choose them from your device</span>
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
            {notice && (
              <p className="notice" role="alert">
                {notice}
              </p>
            )}
            <fieldset className="model-selector" disabled={busy}>
              <legend>Models for the next analysis</legend>
              <p>Choose one or both. Both are selected by default.</p>
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
                    <small id={`${key}-credit`}>{MODEL_INFO[key].credit}</small>
                  </span>
                </label>
              ))}
              <p className="selector-note">
                At least one model stays selected. Changing this choice does not
                change earlier results.
              </p>
            </fieldset>
            <div className="privacy-note">
              <span aria-hidden="true">◎</span>
              <p>
                <strong>Local privacy:</strong> This version sends images to the
                backend on your PC. The app does not save original files or
                results.
              </p>
            </div>
          </section>
          <section className="results-panel" aria-labelledby="results-title">
            <div className="section-heading">
              <span className="step">02</span>
              <div>
                <h2 id="results-title">Review results</h2>
                <p>
                  Known origin and predictions should be checked separately.
                </p>
              </div>
            </div>
            {items.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon" aria-hidden="true">
                  ◇
                </div>
                <h3>Your analysis starts here</h3>
                <p>
                  Selected images appear here with a preview, processing state,
                  and model scores.
                </p>
              </div>
            ) : (
              <>
                <div className="batch-actions">
                  <span>
                    {items.length} of {MAX_FILES} images selected
                  </span>
                  <div>
                    {completed.length > 0 && (
                      <button className="text-button" onClick={exportCsv}>
                        Export CSV
                      </button>
                    )}
                    {pending.length > 0 && (
                      <button
                        className="primary small"
                        disabled={busy}
                        onClick={() => run(pending.map((item) => item.id))}
                      >
                        {busy
                          ? "Processing…"
                          : `Analyze ${pending.length} ${pending.length === 1 ? "image" : "images"}`}
                      </button>
                    )}
                  </div>
                </div>
                <div className="result-list">
                  {items.map((item) => (
                    <article className="result-card" key={item.id}>
                      <img
                        src={item.preview}
                        alt={`Preview of ${item.file.name}`}
                      />
                      <div className="result-body">
                        <div className="result-top">
                          <div>
                            <h3 title={item.file.name}>{item.file.name}</h3>
                            <span className="file-meta">
                              {niceSize(item.file.size)} ·{" "}
                              {item.file.type.split("/")[1]?.toUpperCase()}
                            </span>
                          </div>
                          <button
                            className="remove"
                            title="Remove image"
                            aria-label={`Remove ${item.file.name}`}
                            disabled={busy}
                            onClick={() => remove(item.id)}
                          >
                            ×
                          </button>
                        </div>
                        {item.state === "ready" && (
                          <p className="state ready">Ready to analyze</p>
                        )}
                        {item.state === "processing" && (
                          <p className="state processing" role="status">
                            Analyzing with{" "}
                            {item.runningModels?.map(modelName).join(" and ")}…
                          </p>
                        )}
                        {item.state === "error" && (
                          <p className="state error" role="alert">
                            {item.error}{" "}
                            <button
                              className="text-button"
                              disabled={busy}
                              onClick={() =>
                                run(
                                  [item.id],
                                  item.runningModels ?? selectedModels,
                                  Boolean(item.result),
                                )
                              }
                            >
                              Retry request
                            </button>
                          </p>
                        )}
                        {item.result && (
                          <div className="analysis">
                            <p className="result-scope">
                              Requested:{" "}
                              {item.result.requestedModels
                                .map(modelName)
                                .join(" + ")}
                            </p>
                            {disagreement(item.result) === true && (
                              <p className="disagreement" role="status">
                                The models disagree on this image. Check their
                                separate scores and the image’s known origin if
                                available.
                              </p>
                            )}
                            <div className="model-results">
                              {item.result.requestedModels.map((key) => {
                                const entry = resultFor(item.result!, key);
                                return (
                                  <section
                                    className="model-result"
                                    key={key}
                                    aria-label={`${modelName(key)} result`}
                                  >
                                    <div className="model-result-heading">
                                      <div>
                                        <h4>{modelName(key)}</h4>
                                        <span>{MODEL_INFO[key].credit}</span>
                                      </div>
                                      {entry?.status === "success" && (
                                        <span
                                          className={`prediction ${entry.prediction}`}
                                        >
                                          Suggests{" "}
                                          <strong>
                                            {entry.prediction === "fake"
                                              ? "AI-generated"
                                              : "Real"}
                                          </strong>
                                        </span>
                                      )}
                                    </div>
                                    {entry?.status === "error" && (
                                      <p className="model-error" role="alert">
                                        {entry.error}{" "}
                                        <button
                                          className="text-button"
                                          disabled={busy}
                                          onClick={() =>
                                            run([item.id], [key], true)
                                          }
                                        >
                                          Retry {modelName(key)}
                                        </button>
                                      </p>
                                    )}
                                    {!entry && (
                                      <p className="model-error">
                                        No result returned for this model.
                                      </p>
                                    )}
                                    {entry?.status === "success" && (
                                      <>
                                        <div className="scores">
                                          <div>
                                            <span>
                                              AI-generated model score
                                            </span>
                                            <strong>
                                              {score(entry.model_scores.fake)}
                                            </strong>
                                            <meter
                                              min="0"
                                              max="1"
                                              value={entry.model_scores.fake}
                                            />
                                          </div>
                                          <div>
                                            <span>Real model score</span>
                                            <strong>
                                              {score(entry.model_scores.real)}
                                            </strong>
                                            <meter
                                              min="0"
                                              max="1"
                                              value={entry.model_scores.real}
                                            />
                                          </div>
                                        </div>
                                        <p className="result-meta">
                                          AI flagging cutoff:{" "}
                                          {score(entry.ai_score_threshold)} ·{" "}
                                          {entry.elapsed_ms.toFixed(0)} ms
                                        </p>
                                        <p
                                          className="result-meta model-identity"
                                          title={entry.model_id}
                                        >
                                          Model: {entry.model_id} · revision{" "}
                                          {entry.model_revision}
                                        </p>
                                      </>
                                    )}
                                  </section>
                                );
                              })}
                            </div>
                            <div className="reanalyze">
                              <button
                                className="text-button"
                                disabled={busy}
                                onClick={() => run([item.id])}
                              >
                                Analyze again with current selection
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              </>
            )}
          </section>
        </div>
        <aside className="about">
          <div className="eyebrow">HOW TO READ A COMPARISON</div>
          <h2>Two scores are not a verdict.</h2>
          <p>
            V3 E2 is the owner’s trained fusion model using FFT features and a
            frozen pretrained MobileNetV3 backbone. Community Forensics is an
            external baseline by Thermostatic. Each model uses its own
            preprocessing and decision cutoff. Their scores are not calibrated
            to each other, so a larger number from one model does not mean
            stronger evidence than a smaller number from the other.
          </p>
          <p>
            Both models can be wrong, including when they agree. Disagreement is
            useful to inspect, but neither result proves how an image was made.
            Community Forensics is credited at{" "}
            <a
              href="https://huggingface.co/Thermostatic/community-forensics-frontier-detector-2026-08"
              target="_blank"
              rel="noreferrer"
            >
              its model page
            </a>
            . A fair head-to-head evaluation on independently sourced,
            known-origin images remains to be done.
          </p>
        </aside>
      </main>
      <footer>
        Image Origin Studio · Local release · No account or cloud storage in
        this version
      </footer>
    </div>
  );
}
