import { useId, useState } from "react";
import "./gallery.css";

export type GalleryOrigin = "camera_photo" | "ai_generated";
export type GalleryModelRun = {
  modelKey: "v3_e2" | "community_forensics";
  modelId: string;
  modelRevision: string;
  preprocessingRecipe: string;
  prediction: "fake" | "real";
  aiScore: number;
  threshold: number;
  analyzedAt: string;
};
export type GalleryCase = {
  id: string;
  title: string;
  assetUrl: string;
  origin: GalleryOrigin;
  sourcePage: string;
  sourceName: string;
  attribution: string;
  originEvidence: string;
  rights: string;
  rightsUrl?: string;
  edits: string;
  sha256: string;
  modelRuns: GalleryModelRun[];
};

type GalleryFilter =
  | "all"
  | "camera_photo"
  | "ai_generated"
  | "disagreement"
  | "mistake";

const MODEL_NAMES = {
  v3_e2: "V3 E2",
  community_forensics: "Community Forensics",
} as const;

function documentedOrigin(origin: GalleryOrigin) {
  return origin === "camera_photo" ? "Camera photograph" : "AI-generated image";
}

function modelSuggestion(prediction: GalleryModelRun["prediction"]) {
  return prediction === "fake" ? "AI-generated" : "Real";
}

function conflictsWithRecord(galleryCase: GalleryCase, run: GalleryModelRun) {
  return (
    run.prediction !== (galleryCase.origin === "ai_generated" ? "fake" : "real")
  );
}

function modelsDisagree(galleryCase: GalleryCase) {
  const predictions = galleryCase.modelRuns.map((run) => run.prediction);
  return predictions.length > 1 && new Set(predictions).size > 1;
}

function hasModelMistake(galleryCase: GalleryCase) {
  return galleryCase.modelRuns.some((run) =>
    conflictsWithRecord(galleryCase, run),
  );
}

function matchesFilter(galleryCase: GalleryCase, filter: GalleryFilter) {
  if (filter === "disagreement") return modelsDisagree(galleryCase);
  if (filter === "mistake") return hasModelMistake(galleryCase);
  return filter === "all" || galleryCase.origin === filter;
}

function asPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

type Props = { cases: GalleryCase[] };

export default function Gallery({ cases }: Props) {
  const [filter, setFilter] = useState<GalleryFilter>("all");
  const [guesses, setGuesses] = useState<Record<string, GalleryOrigin>>({});
  const [activeId, setActiveId] = useState("");
  const [revealed, setRevealed] = useState(false);
  const headingPrefix = useId();
  const visibleCases = cases.filter((galleryCase) =>
    matchesFilter(galleryCase, filter),
  );

  function reveal(id: string) {
    if (!guesses[id]) return;
    setActiveId(id);
    setRevealed(true);
  }

  function openCase(id: string) {
    setActiveId(id);
    setRevealed(false);
  }

  const activeCase = visibleCases.find(
    (galleryCase) => galleryCase.id === activeId,
  );

  return (
    <section
      id="challenge-gallery"
      className="gallery"
      aria-labelledby="gallery-title"
    >
      <div className="gallery-intro">
        <div>
          <p className="eyebrow">LOCAL REVIEW DRAFT · NOT PUBLISHED</p>
          <h2 id="gallery-title">Try a source-documented image</h2>
          <p>
            Make a private guess, then reveal the source record and each model’s
            suggestion. Guesses stay in this browser tab. These selected cases
            demonstrate behavior; they do not measure either model’s accuracy.
          </p>
        </div>
        {cases.length > 0 && (
          <div className="gallery-filter">
            <label htmlFor="gallery-filter">Show cases</label>
            <select
              id="gallery-filter"
              value={filter}
              onChange={(event) =>
                setFilter(event.target.value as GalleryFilter)
              }
            >
              <option value="all">All cases</option>
              <option value="camera_photo">Documented camera photos</option>
              <option value="ai_generated">Documented AI images</option>
              <option value="disagreement">Models disagree</option>
              <option value="mistake">A model conflicts with source</option>
            </select>
            <span aria-live="polite">
              {visibleCases.length} of {cases.length} cases shown
            </span>
          </div>
        )}
      </div>
      <p className="gallery-caution">
        These source-documented examples are product demonstrations, not an
        accuracy measure. Your guesses stay in this tab.
      </p>
      {cases.length === 0 ? (
        <p className="gallery-empty">
          The gallery is being prepared. Cases will appear after their sources,
          origin records, and display rights have been reviewed.
        </p>
      ) : visibleCases.length === 0 ? (
        <p className="gallery-empty">No candidate cases match this filter.</p>
      ) : activeCase ? (
        (() => {
          const galleryCase = activeCase;
          const caseNumber =
            cases.findIndex((candidate) => candidate.id === galleryCase.id) + 1;
          const titleId = `${headingPrefix}-case-${galleryCase.id}`;
          const guess = guesses[galleryCase.id];
          return (
            <>
              <button
                className="gallery-back"
                type="button"
                onClick={() => setActiveId("")}
              >
                ← All cases
              </button>
              <article
                className="gallery-case-view"
                key={galleryCase.id}
                aria-labelledby={titleId}
              >
                <figure className="gallery-image">
                  <img
                    src={galleryCase.assetUrl}
                    alt={galleryCase.title}
                    loading="lazy"
                  />
                  <figcaption>
                    Case {String(caseNumber).padStart(2, "0")}
                  </figcaption>
                </figure>
                <div className="gallery-card-body">
                  <h3 id={titleId}>{galleryCase.title}</h3>
                  <fieldset className="gallery-guess" disabled={revealed}>
                    <legend>Your private guess</legend>
                    <label>
                      <input
                        type="radio"
                        name={`gallery-guess-${galleryCase.id}`}
                        value="camera_photo"
                        checked={guess === "camera_photo"}
                        onChange={() =>
                          setGuesses((previous) => ({
                            ...previous,
                            [galleryCase.id]: "camera_photo",
                          }))
                        }
                      />
                      Camera photograph
                    </label>
                    <label>
                      <input
                        type="radio"
                        name={`gallery-guess-${galleryCase.id}`}
                        value="ai_generated"
                        checked={guess === "ai_generated"}
                        onChange={() =>
                          setGuesses((previous) => ({
                            ...previous,
                            [galleryCase.id]: "ai_generated",
                          }))
                        }
                      />
                      AI-generated image
                    </label>
                  </fieldset>
                  {!revealed && (
                    <button
                      className="gallery-reveal"
                      type="button"
                      disabled={!guess}
                      onClick={() => reveal(galleryCase.id)}
                    >
                      Reveal source and model suggestions
                    </button>
                  )}
                  {revealed && (
                    <div className="gallery-revealed" aria-live="polite">
                      <p className="gallery-origin">
                        <span>Documented origin</span>
                        <strong>{documentedOrigin(galleryCase.origin)}</strong>
                      </p>
                      <p className="gallery-your-guess">
                        Your guess:{" "}
                        {guess ? documentedOrigin(guess) : "No guess recorded"}.
                        This is private and is not saved or scored.
                      </p>
                      {modelsDisagree(galleryCase) && (
                        <p className="gallery-observation">
                          The models disagree on this case.
                        </p>
                      )}
                      {hasModelMistake(galleryCase) && (
                        <p className="gallery-observation">
                          At least one model suggestion conflicts with the
                          documented origin.
                        </p>
                      )}
                      <div className="gallery-models">
                        {galleryCase.modelRuns.map((run) => (
                          <section
                            key={run.modelKey}
                            aria-label={`${MODEL_NAMES[run.modelKey]} suggestion`}
                          >
                            <h4>{MODEL_NAMES[run.modelKey]}</h4>
                            <p>
                              Suggests{" "}
                              <strong>{modelSuggestion(run.prediction)}</strong>
                            </p>
                            <p>
                              AI model score {asPercent(run.aiScore)} · AI
                              flagging cutoff {asPercent(run.threshold)}
                            </p>
                            {conflictsWithRecord(galleryCase, run) && (
                              <p className="gallery-mistake">
                                Conflicts with source record
                              </p>
                            )}
                            <details>
                              <summary>Model and processing details</summary>
                              <p>Model: {run.modelId}</p>
                              <p>Revision: {run.modelRevision}</p>
                              <p>Recipe: {run.preprocessingRecipe}</p>
                              <p>Analyzed: {run.analyzedAt}</p>
                            </details>
                          </section>
                        ))}
                      </div>
                      <details className="gallery-source">
                        <summary>Source and technical record</summary>
                        <h4>Source record</h4>
                        <p>
                          <a
                            href={galleryCase.sourcePage}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {galleryCase.sourceName}
                          </a>
                        </p>
                        <p>
                          <strong>Origin evidence:</strong>{" "}
                          {galleryCase.originEvidence}
                        </p>
                        <p>
                          <strong>Attribution:</strong>{" "}
                          {galleryCase.attribution}
                        </p>
                        <p>
                          <strong>Display rights:</strong> {galleryCase.rights}{" "}
                          {galleryCase.rightsUrl && (
                            <a
                              href={galleryCase.rightsUrl}
                              target="_blank"
                              rel="noreferrer"
                            >
                              License
                            </a>
                          )}
                        </p>
                        <p>
                          <strong>Edits:</strong> {galleryCase.edits}
                        </p>
                        <p className="gallery-hash">
                          <strong>Displayed file SHA-256:</strong>{" "}
                          {galleryCase.sha256}
                        </p>
                      </details>
                    </div>
                  )}
                </div>
              </article>
            </>
          );
        })()
      ) : (
        <div className="gallery-grid">
          {visibleCases.map((galleryCase) => {
            const caseNumber =
              cases.findIndex((candidate) => candidate.id === galleryCase.id) +
              1;
            return (
              <button
                type="button"
                className="gallery-card"
                key={galleryCase.id}
                onClick={() => openCase(galleryCase.id)}
                aria-label={`Inspect case ${caseNumber}: ${galleryCase.title}`}
              >
                <figure className="gallery-image">
                  <img src={galleryCase.assetUrl} alt="" loading="lazy" />
                  <figcaption>
                    Case {String(caseNumber).padStart(2, "0")}
                  </figcaption>
                </figure>
                <span className="gallery-card-title">{galleryCase.title}</span>
                <span className="gallery-open">Inspect case →</span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
