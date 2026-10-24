# Making Image Origin Studio more useful and distinctive

Research and product direction, 24 October 2026. These are **proposals**, not
features implemented in the current app. The local comparison works, while
the [public paired pilot](PUBLIC_PILOT_2026-10-24.md) exposed V3 E2 mistakes
on unfamiliar sources. The strongest direction is an **evidence workbench**:
help a person understand the image, the two model suggestions, and the limits
of each signal. That makes the owner's trained model and engineering work
visible without promising that an AI detector can prove origin.

## Recommended product path

| Priority | Idea | What the user experiences | Why it adds value | Scope |
| --- | --- | --- | --- | --- |
| 1 | **Case report and input-view inspector** | After upload, inspect the exact crop/resize each model received, then download a local report with image hash, model versions, thresholds, scores, errors, and caveats. | Makes the model pipeline understandable and the result reproducible. Avoid calling crop previews explanations of model reasoning. | Medium |
| 2 | **Known-origin challenge gallery** | Guess whether a licensed example is camera-made or generated, reveal its documented source, then see both model suggestions and their mistakes. Filter for disagreements and false alarms. | An engaging demonstration that teaches why a detector can fail. It also gives the UI a useful state before a visitor uploads private images. | Medium; needs carefully licensed and checked examples |
| 3 | **Robustness lab** | On one uploaded image, try declared JPEG, resize, and crop variants. Show how each model's score and decision change in a small chart. Keep the original beside the transformed view. | Transformation sensitivity is a real research problem; making it visible is more honest and interesting than another confidence gauge. | Medium to high; needs limits on CPU work |
| 4 | **Provenance panel** | Check for a verifiable C2PA Content Credential, show issuer/actions and validation state, and keep it separate from the two model scores. Show “no credential found” as unknown. | Adds an independent kind of evidence and a clear lesson about provenance versus statistical screening. | Medium; validate SDK, supported formats, and privacy behavior first |
| 5 | **Evaluation observatory** | A public page for dated, frozen evaluation runs with source mix, confusion counts, false alarms, subgroup slices, and a browsable failure gallery. | Supports a defensible resume story and makes limitations easy to inspect. | Medium after a larger independent set |
| 6 | **AWS job workflow** | Larger batches become jobs with progress, retries, private deletion controls, and a clear completion receipt. | Demonstrates production engineering, but host choice and cost must follow measured memory and runtime. | High; later release |

The first three could form one coherent **Image Origin Lab** screen: results,
what each model saw, and what happens when the image is transformed. A case
report would capture the exact experiment. The gallery could be a separate
guided route. Build one vertical slice at a time and test it on desktop,
phone, keyboard, and slow/error states.

## Research behind the choices

- The [NTIRE 2026 robust detection
  challenge](https://arxiv.org/abs/2604.11487) explicitly evaluates generated
  image detectors on cropped, resized, compressed, and blurred images. A
  robustness lab is a grounded interaction, provided it shows transformed
  bytes and does not suggest that changing an image reveals its true origin.
- An [open-model benchmark
  study](https://arxiv.org/abs/2602.07814) reports unstable rankings across
  datasets and large variation with training-data alignment. This supports
  showing source-specific mistakes and avoiding a universal “winner” badge.
- The [C2PA specification](https://spec.c2pa.org/specifications/) describes
  signed provenance. Its [explainer](https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html)
  says provenance can be incomplete and does not establish that depicted
  content is true. The Content Authenticity Initiative's
  [web SDK](https://github.com/contentauth/c2pa-js/blob/main/packages/c2pa-web/README.md)
  is a plausible integration route; inspect validation and trust semantics
  before choosing implementation details. Absence of a credential must never
  be labeled “real” or “fake.”
- [NIST's image detector evaluation
  plan](https://ai-challenges.nist.gov/pub/GenAI_Image_Discriminators_Evalplan.pdf)
  keeps test media out of training, selection, and tuning. A frozen run page
  should preserve this separation and display errors alongside scores.
- [WCAG 2.2](https://www.w3.org/TR/wcag/) provides the accessibility baseline
  for status messages, keyboard use, labels, and visible focus. The current
  result cards provide a useful start; challenge and transformation controls
  must remain usable without a mouse.
- [AWS's asynchronous job
  pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/process-events-asynchronously-with-amazon-api-gateway-amazon-sqs-and-aws-fargate.html)
  is an example for queue-backed processing. It is an architecture option,
  not evidence that these exact services fit our model sizes or budget.

## Decisions and gates

1. **Choose the first vertical slice.** I recommend the case report and
   input-view inspector. It uses the current app, is directly useful during
   the larger evaluation, and can be checked without collecting accounts or
   storing uploads.
2. **Build the gallery from independently checked examples.** The current
   12-image public pilot is too narrow to present as a general challenge.
   Record individual licenses, source pages, hashes, and known origins;
   show incorrect predictions rather than selecting flattering examples.
3. **Keep experimentation separate from verdicts.** The robustness lab
   should show score changes for declared transformations. It should not
   silently retune thresholds, use user uploads for training, or generate a
   stronger-looking combined score.
4. **Measure before cloud work.** CPU memory, cold startup, batch time,
   traffic assumptions, storage retention, and current AWS prices set the
   deployment design. Review a cost estimate, budget alert, and teardown
   before any paid resources are provisioned.

Ideas to avoid for now: a single “authenticity percentage,” unvalidated
heatmaps that imply the model found a manipulated region, a universal model
ranking from the 12-image pilot, and permanent upload history before
ownership/deletion rules exist.
