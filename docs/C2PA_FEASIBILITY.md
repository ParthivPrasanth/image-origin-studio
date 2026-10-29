# Content Credentials prototype

**Status:** local feasibility prototype, 25 October 2026. Every uploaded
image card offers **Check credentials**. The result stays separate from
both model suggestions.
The owner has checked the C2PA flow in the app and subsequently confirmed the
edge behavior. The table below distinguishes recorded case-specific checks
from that broader review; the owner's latest fixture details were not recorded.

## How it works

- The browser lazy-loads official `@contentauth/c2pa-web` version `0.15.4`
  and its locally bundled WebAssembly file. Validation reads the original
  `File` before model preprocessing. No image bytes go to a C2PA service.
- The bundled [C2PA trust list](https://github.com/c2pa-org/conformance-public/blob/main/trust-list/C2PA-TRUST-LIST.pem)
  is `frontend/public/c2pa/anchors.pem`, fetched 25 October 2026.
  SHA-256: `b3949271a07b007e92ef1d18050b55388f5e0d2686a16fd864176c48421af8ae`.
  This snapshot needs a refresh process before public release.
- The panel distinguishes trusted, valid with unresolved signer trust,
  invalid, absent, unsupported, and validation error. Signer, issuer, actions,
  and AI-generation declarations appear only for validated credentials.
  No credential means unknown origin.
- A validated `c2pa.actions` assertion with `trainedAlgorithmicMedia` appears
  as an AI-generation claim. The reader checks the active manifest and its
  validated `parentOf` chain, since a later edit can declare `composite` while
  the original creation declares AI generation. The panel identifies an
  earlier origin claim separately from the active edit actions. If a model
  suggests real, it names the conflict while keeping that model's suggestion
  and score. The case report exports credentials separately.

## Local checks

| Input | Source | Observed result |
| --- | --- | --- |
| Signed AI JPEG | [Content Authenticity Initiative Firefly sample](https://github.com/contentauth/example-assets/blob/main/images/Firefly_tabby_cat.jpg) | **Valid**, Adobe Firefly C2PA signer, AI-generation claim; signer trust unresolved against current C2PA list |
| Same JPEG with one image-data byte changed | Local altered copy, ignored under `.local/c2pa-fixtures/` | **Invalid**; origin claim withheld |
| Unsigned USGS gallery JPEG | Local gallery display file | **No credential found**; origin unknown from C2PA |
| Unsigned WebP made from the public bird gallery display JPEG | Disposable local browser fixture, 26 October | **No credential found**; WebP was processed by the validator, so it is not an unsupported-format example |
| Print-friendly case report | Firefly sample after model analysis | Credential status, signer, claim, SDK version, and trust-list status appear separately from both models |
| Three original Gemini PNGs | Owner's local test folder | **Trusted**; active edit is `composite`, while validated parent manifests declare AI generation. All three now show the earlier AI-origin claim. |
| Four previously generated ChatGPT PNGs | Ignored local gallery originals | One **Trusted** with an active AI-generation claim. Three **Invalid** due to `signingCredential.invalid` and `signingCredential.untrusted`; their claims are withheld in the app. |
| Original camping-mug ImageGen PNG in browser History, 26 October | Ignored local original; disposable saved copy | **Trusted** active AI-generation claim. Real V3 E2 suggested AI-generated, so this is not a real conflict. |
| Same signed camping-mug bytes with a local test-only V3 E2 stub suggesting real | Disposable localhost API and History; [UI capture](../output/review/release-sweep-c2pa-conflict-stub.png) | Conflict message displayed the validated claim separately from the stubbed model suggestion. The stub score is synthetic UI data. |

Both models suggested AI-generated for the Firefly sample. The Gemini and
ChatGPT cases above were checked directly with the same installed C2PA WASM
engine and bundled trust list against original file bytes. The trusted
camping-mug case and three invalid ImageGen originals were then exercised in
the browser on 26 October. A validated credential with a **real pinned-model**
real suggestion was not captured in that independent run; only the controlled
stub exercised the conflict UI there. The owner subsequently reported
verifying the edge behavior. The upload UI accepts
JPEG, PNG, and WebP, and the new WebP check did not reach the unsupported state.
There is currently no browser route to submit a genuinely unsupported format
through the analysis screen.

Newly downloaded case reports use schema `image-origin-case-report/v2` and
include a separate `content_credentials` field. Older sample reports under
`output/` predate this prototype and use the previous schema.

The credential validates a signed claim and its connection to the file; it
does not prove that the depicted scene is true. Neither credential nor model
result rewrites the other.

References: [browser SDK](https://github.com/contentauth/c2pa-js/blob/main/packages/c2pa-web/README.md),
[validation states](https://opensource.contentauthenticity.org/docs/manifest/reading/manifest-validation/),
and [C2PA explainer](https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html).
