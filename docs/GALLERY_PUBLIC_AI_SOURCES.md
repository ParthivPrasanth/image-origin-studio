# Public AI-image gallery sources

**Status:** four curated cases acquired 25 October 2026; the owner marked the
gallery ready for public inclusion on 26 October 2026. These are
public [COCOXGEN dataset](https://huggingface.co/datasets/heikeadel/cocoxgen)
images by Philipp Moeßner and Heike Adel, distributed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The dataset identifies
the `sdxl` and `fooocus` folders as generated images. The gallery shows resized
and re-encoded copies; the original source bytes remain in the read-only sibling
ML Project and are not required by this app at runtime.

| Case | Public source file | Generator | Source SHA-256 | Display SHA-256 |
| --- | --- | --- | --- | --- |
| Traffic lights | `sdxl/558558-short-sdxl.jpg` | SDXL | `a656e67b7e926f5187078af3220de4c6209204133541baca360e3fcc7a64a876` | `353664928a2f9db88c1ff591f4f14adda1750f6bb981ad2f58a9cb007762134e` |
| Skier in snow | `sdxl/445602-long-sdxl.jpg` | SDXL | `e8cb1e706aac0f44c34c1b8a01b406c588caf1ee62d97214f1ede8dca1351590` | `fafe941ef72614a14cda8afee53d486ae4333bd05a51da193b9bb010f8bbd241` |
| Bananas on a chair | `sdxl/279769-short-sdxl.jpg` | SDXL | `7543827a74ad57bd78dbbeccc67ad262c634134fec50ba6c6858d17e1413964d` | `29655a2a0a5acc904d57f4da69e03a3e1a2fd4b3cc77c5f691f9548aff08898f` |
| Tennis player | `fooocus/19432-long-fooocus.png` | Fooocus | `67aa4363af27281c6344fefa13251d2ea13071ab9d5a40be7d06e0ffbdb2cd2c` | `54c9f5bd085fe61b391e7cd3d5f2ef99e89d8da8f35bcba3f4d01aa8b9520cd8` |

Dataset revision: `c336ad187c2ab298ce825df65088bdacbae104f6`.
The source files were transformed by applying EXIF orientation, converting to
RGB, resizing to fit within 1200 × 1200 with Lanczos, and encoding JPEG quality
88 with no crop or retouch. Exact displayed files and pinned model runs are in
[GALLERY_MANIFEST.json](GALLERY_MANIFEST.json).

The four examples were selected after scoring candidate images on the current
V3 E2 and Community Forensics models. Three V3 E2 suggestions identify the AI
origin and one misses it. COCOXGEN is also a source family used in V3 E2 model
development, so this curated gallery demonstrates the product experience and
does not measure general detection performance or establish whether any
particular image was seen during training.
