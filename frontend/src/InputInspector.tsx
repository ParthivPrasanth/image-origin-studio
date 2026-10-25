import { useEffect, useRef, useState } from "react";
import { inspect } from "./api";
import {
  modelName,
  type ComparisonResult,
  type InspectionResponse,
  type ModelKey,
} from "./types";

type Props = {
  file: File;
  result: ComparisonResult;
  id: string;
};

export default function InputInspector({ file, result, id }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [inspection, setInspection] = useState<InspectionResponse>();
  const controller = useRef<AbortController | null>(null);
  const successful = result.requestedModels.filter((key) =>
    result.models.some(
      (entry) => entry.model_key === key && entry.status === "success",
    ),
  ) as ModelKey[];
  const failed = result.requestedModels.filter(
    (key) => !successful.includes(key),
  );

  useEffect(() => () => controller.current?.abort(), []);

  async function toggle() {
    if (open) {
      controller.current?.abort();
      controller.current = null;
      setOpen(false);
      setLoading(false);
      setInspection(undefined);
      setError("");
      return;
    }
    setOpen(true);
    setLoading(true);
    setError("");
    const current = new AbortController();
    controller.current = current;
    try {
      const response = await inspect(file, successful, current.signal);
      if (response.input.sha256 !== result.input.sha256) {
        throw new Error("The file bytes no longer match the analyzed image.");
      }
      if (!current.signal.aborted) setInspection(response);
    } catch (cause) {
      if (!current.signal.aborted) {
        setError(cause instanceof Error ? cause.message : "Inspection failed.");
      }
    } finally {
      if (!current.signal.aborted) setLoading(false);
    }
  }

  return (
    <div className="inspector-wrap">
      {successful.length === 0 ? (
        <p className="inspector-note">
          Input views become available after a model succeeds.
        </p>
      ) : (
        <button
          type="button"
          className="text-button"
          aria-expanded={open}
          aria-controls={`inspector-${id}`}
          onClick={toggle}
        >
          {open ? "Close input inspector" : "Inspect model inputs"}
        </button>
      )}
      {open && (
        <section
          className="inspector"
          id={`inspector-${id}`}
          aria-label="Model input views"
        >
          <h4>What each pipeline receives</h4>
          <p>
            These display previews show the pixel view before tensor
            normalization. They do not explain why a model made its suggestion.
          </p>
          {failed.length > 0 && (
            <p className="inspector-note">
              No successful analysis for {failed.map(modelName).join(" and ")};
              its input view is omitted.
            </p>
          )}
          {loading && <p role="status">Preparing input views…</p>}
          {error && (
            <p role="alert" className="model-error">
              {error}
            </p>
          )}
          {inspection && (
            <>
              <p className="result-meta">
                Original file: {inspection.input.width} ×{" "}
                {inspection.input.height} pixels ·{" "}
                {inspection.input.image_format}
              </p>
              <div className="inspection-grid">
                {inspection.views.map((view) => (
                  <figure key={view.key} className="inspection-view">
                    <img
                      src={view.preview_data_url}
                      alt={`${view.title} display preview`}
                    />
                    <figcaption>
                      <strong>{view.title}</strong>
                      <span>
                        {view.width} × {view.height} pixels · {view.recipe_id}
                      </span>
                      <span>{view.description}</span>
                      {view.note && <em>{view.note}</em>}
                    </figcaption>
                  </figure>
                ))}
              </div>
            </>
          )}
        </section>
      )}
    </div>
  );
}
