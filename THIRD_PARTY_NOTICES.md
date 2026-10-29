# Third-party material and attribution

The repository's [MIT License](LICENSE) covers project-owned code, documentation, and the packaged V3 E2 fusion artifact. It does not override the terms of independently sourced model weights, datasets, gallery images, or dependencies.

| Material | Where it appears | Source and rights record |
| --- | --- | --- |
| Community Forensics ONNX baseline | Downloaded at runtime; not committed | [Thermostatic model card](https://huggingface.co/Thermostatic/community-forensics-frontier-detector-2026-08), revision `16db135220b318d811b207db576d90368980b595`, published as MIT. The app verifies the pinned weights before loading. |
| MobileNetV3-Small ImageNet pretrained weights | Downloaded at runtime; not committed | [TorchVision model/weight documentation](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html). The [artifact record](backend/artifacts/README.md) gives the expected SHA-256 and source URL. Review the upstream and dataset-derived terms before redistributing the weights. |
| Four generated gallery display images | `frontend/public/gallery/candidates/` | [COCOXGEN](https://huggingface.co/datasets/heikeadel/cocoxgen) by Philipp Moeßner and Heike Adel, **CC BY 4.0**. [Per-image credit, revision, transformations, and hashes](docs/GALLERY_PUBLIC_AI_SOURCES.md). |
| Four camera-photo gallery display images | `frontend/public/gallery/candidates/` | Individual USGS pages mark the source photographs **Public Domain**. Named photographers and office credits, source links, transformations, and hashes are in the [camera-photo source record](docs/GALLERY_CAMERA_SOURCES.md). |
| Browser C2PA trust-anchor snapshot | `frontend/public/c2pa/anchors.pem` | A public certificate/trust-anchor bundle used by the credential prototype, not a private key. Its limitations and update needs are documented in [C2PA feasibility](docs/C2PA_FEASIBILITY.md). |
| Python and JavaScript packages | Installed from lockfiles; dependency sources are not committed | Direct dependencies are in `backend/requirements.txt`, exact Python packages in `backend/requirements-lock.txt`, and npm packages in `frontend/package.json` and `frontend/package-lock.json`. Each dependency retains its own license. |

The gallery's [machine-readable manifest](docs/GALLERY_MANIFEST.json) connects every displayed case to its source record, rights, display hash, and model suggestions. The selected examples show product behavior and are not a representative accuracy sample. `output/` contains dated local review artifacts; it is not a license grant for the third-party content visible in those captures.
