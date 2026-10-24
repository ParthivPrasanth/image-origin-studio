import { useEffect, useRef, useState } from "react";

type Result = {
  prediction: "fake" | "real";
  model_scores: { fake: number; real: number };
  model_id: string;
  model_revision: string;
  ai_score_threshold: number;
  elapsed_ms: number;
  image_format: string;
};
type Item = {
  id: string;
  file: File;
  preview: string;
  state: "ready" | "processing" | "done" | "error";
  result?: Result;
  error?: string;
};
const MAX_FILES = 8;
const MAX_BYTES = 10 * 1024 * 1024;

function niceSize(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
function score(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

async function analyze(file: File): Promise<Result> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/analyze", { method: "POST", body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export default function App() {
  const [items, setItems] = useState<Item[]>([]);
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
    if (selected.length > room)
      setNotice(
        `Only the first ${room} files were added. The batch limit is ${MAX_FILES}.`,
      );
    else if (accepted.length === selected.length) setNotice("");
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

  async function run(ids: string[]) {
    if (busy) return;
    setBusy(true);
    for (const id of ids) {
      const item = itemsRef.current.find((candidate) => candidate.id === id);
      if (!item) continue;
      setItems((previous) =>
        previous.map((candidate) =>
          candidate.id === id
            ? { ...candidate, state: "processing", error: undefined }
            : candidate,
        ),
      );
      try {
        const result = await analyze(item.file);
        setItems((previous) =>
          previous.map((candidate) =>
            candidate.id === id
              ? { ...candidate, state: "done", result }
              : candidate,
          ),
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
    const rows = [
      [
        "file",
        "prediction",
        "fake_model_score",
        "real_model_score",
        "model_id",
        "model_revision",
        "ai_score_threshold",
        "elapsed_ms",
      ],
      ...items
        .filter((item) => item.result)
        .map((item) => [
          item.file.name,
          item.result!.prediction,
          String(item.result!.model_scores.fake),
          String(item.result!.model_scores.real),
          item.result!.model_id,
          item.result!.model_revision,
          String(item.result!.ai_score_threshold),
          String(item.result!.elapsed_ms),
        ]),
    ];
    // Spreadsheet programs may treat a filename beginning with =, +, - or @ as a formula.
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
    link.download = "image-origin-results.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  const pending = items.filter(
    (item) => item.state === "ready" || item.state === "error",
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
          <h1>Explore what the model sees.</h1>
          <p>
            Upload a photograph or generated image to inspect an experimental
            model’s score. It made mistakes in a small dataset-labeled check, so
            use its result as a clue, never proof of an image’s origin.
          </p>
        </section>
        <div className="workspace">
          <section className="upload-panel" aria-labelledby="upload-title">
            <div className="section-heading">
              <span className="step">01</span>
              <div>
                <h2 id="upload-title">Choose images</h2>
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
                <p>Known origin and prediction should be checked separately.</p>
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
                            Analyzing image…
                          </p>
                        )}
                        {item.state === "error" && (
                          <p className="state error" role="alert">
                            {item.error}{" "}
                            <button
                              className="text-button"
                              disabled={busy}
                              onClick={() => run([item.id])}
                            >
                              Retry
                            </button>
                          </p>
                        )}
                        {item.result && (
                          <div className="analysis">
                            <p
                              className={`prediction ${item.result.prediction}`}
                            >
                              Experimental model suggests{" "}
                              <strong>
                                {item.result.prediction === "fake"
                                  ? "AI-generated"
                                  : "Real"}
                              </strong>
                            </p>
                            <div className="scores">
                              <div>
                                <span>AI-generated model score</span>
                                <strong>
                                  {score(item.result.model_scores.fake)}
                                </strong>
                                <meter
                                  min="0"
                                  max="1"
                                  value={item.result.model_scores.fake}
                                />
                              </div>
                              <div>
                                <span>Complementary real score</span>
                                <strong>
                                  {score(item.result.model_scores.real)}
                                </strong>
                                <meter
                                  min="0"
                                  max="1"
                                  value={item.result.model_scores.real}
                                />
                              </div>
                            </div>
                            <p className="result-meta">
                              AI flagging cutoff:{" "}
                              {score(item.result.ai_score_threshold)}. Scores
                              are estimates, not certainty.
                            </p>
                            <p className="result-meta">
                              Model revision{" "}
                              {item.result.model_revision.slice(0, 8)} ·{" "}
                              {item.result.elapsed_ms.toFixed(0)} ms
                            </p>
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
          <div className="eyebrow">HOW TO READ A RESULT</div>
          <h2>A score is not a verdict.</h2>
          <p>
            The AI score is calibrated on the model author’s development data;
            the real score is its complement. The published 65% cutoff decides
            the label. A high score can still be wrong, especially for
            unfamiliar generators, edits, or images unlike its training data.
          </p>
          <p>
            Model:{" "}
            <a
              href="https://huggingface.co/Thermostatic/community-forensics-frontier-detector-2026-08"
              target="_blank"
              rel="noreferrer"
            >
              Thermostatic/community-forensics-frontier-detector-2026-08
            </a>
            . In one separate 60-image check, this app got 25 of 30 real and 26
            of 30 fully generated images right. That small sample does not
            predict performance on your uploads.
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
