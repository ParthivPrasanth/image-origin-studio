# V3 E2 inference artifact

`v3_e2.npz` contains only the owner's trained V3 E2 fusion-head tensors and
the two training-fitted scaler vectors. It was exported from the locked V3
candidate artifact in the separate ML Project. It contains no source images,
training data, or other V3 candidates. The ML Project is never read at runtime.

| Item | SHA-256 |
| --- | --- |
| Locked source `outputs/v3/candidate_artifacts.joblib` | `e560a8a20a84e45ca096271ffdf3b590eb43d79cbe5fd28ed7f639591ad41e4b` |
| Packaged `v3_e2.npz` | `7b18530b038cac4332095b00bf04690e91c79c15d0ae9acfe32d22187852fa5c` |
| Official MobileNetV3-Small ImageNet weights | `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f` |

The official pretrained weights are downloaded separately from
`https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth` to the
ignored `model-cache/` directory and hash-checked before loading. Review their
original terms before redistribution; this repository does not bundle them.

To regenerate the NPZ from a trusted copy of the source artifact, use the ML
Project's Python environment:

```powershell
$mlProject = "C:\path\to\ML Project"
& "$mlProject\.venv\Scripts\python.exe" scripts/package_v3_e2.py `
  "$mlProject\outputs\v3\candidate_artifacts.joblib" `
  backend\artifacts\v3_e2.npz
```

`scripts/verify_v3_e2_parity.py` compares the packaged inference path with
the original pipeline on already-viewed V3 final images. This is a code parity
check, not a new accuracy result.
