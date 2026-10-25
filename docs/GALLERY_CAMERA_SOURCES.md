# Camera-photo gallery candidates — source and rights record

**Status:** four local review candidates acquired 25 October 2026. Each
source page is an individual U.S. Geological Survey (USGS) photography record
that explicitly marks the image **Public Domain**. The page's photography
classification, description, institutional provenance, and photographer or
publishing office support a camera-photo label. We have not obtained a camera
RAW or independently verified capture. The gallery labels therefore say
**documented camera photograph** rather than proof of capture.

These files are used in a source-documented product demonstration, not an
evaluation sample. The owner must approve the exact cases, source labels,
attribution, and reveal wording before public release.

| Case | Source page and creator credit | Acquired source copy | Source SHA-256 | Display SHA-256 |
| --- | --- | --- | --- | --- |
| Waterfall | [USGS: Waterfall in Appalachian Forest](https://www.usgs.gov/media/images/waterfall-appalachian-forest), Samuel H Austin | [Original JPEG](https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/thumbnails/image/Austin-Water.jpg), 4288 × 2848 | `65856c738409f567a6ab48d7b383f52281e567a79dfbe7152d31f833a32f0c66` | `e6409a3f92436161989061930819a0442caa52eeee05d4a91e3d3dc3fe01aa9b` |
| Bird | [USGS: Sitting Pretty](https://www.usgs.gov/media/images/sitting-pretty), Amy Tolcin | [USGS full-width page rendition](https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/styles/full_width/public/Sitting_Pretty.jpg?itok=sJpR4z4p), 800 × 531 | `fdc3abf3060f83a50e4678c9140df49fe70929cf6700348b8a5ae4cb64c81392` | `e2dc4f164ebdf067fbb4fee1c70c5f8afdbf65b4990cdcf990e4a3e2748fbe9d` |
| Dunes | [USGS: Desert sand dunes](https://www.usgs.gov/media/images/desert-sand-dunes), Pacific Coastal and Marine Science Center; individual photographer not listed | [USGS full-width page rendition](https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/styles/full_width/public/thumbnails/image/sand-desert.jpg?itok=CQjsGRsK), 600 × 446 | `3f6c6b0bfd2e29cc18e000c4c9f2e16fc3cf14fe35a3c5c7890e948b35a13526` | `a5cdf0e8ce5eaa6e0c6dd35853a460d36d5426cdce644f6b5c81b53826637c46` |
| Bridge | [USGS: Key Bridge](https://www.usgs.gov/media/images/key-bridge), Office of Communications; individual photographer not listed on current page | [USGS full-width page rendition](https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/s3fs-public/styles/full_width/public/DSC00733.JPG?itok=TGiMKAQq), 1336 × 1002 | `bdaf4e378a66307e39323ad52c2c1890db57826a93730483c9f32462642a1119` | `504cd9eda877c0722469c06a7e75368d0e1d9fee706d21485631d9bde67bba14` |

The source copies are retained in ignored `.local/gallery-real-source-copies/`.
The app includes only `frontend/public/gallery/candidates/*-display.jpg`.
`scripts/prepare_gallery_display.py` applies EXIF orientation, converts to RGB,
resizes to fit within 1200 × 1200 pixels with Lanczos, and encodes JPEG quality
88 with 4:4:4 chroma subsampling. There was no crop, retouch, compositing, or
added text. All four were re-encoded; only the waterfall and bridge were
downscaled. The displayed JPEG bytes were scored with both pinned models.

Each individual USGS page marks its image Public Domain. The gallery credits
the named photographer where the page gives one and otherwise credits the
publishing USGS office. No USGS logo is copied into the app. The image
attribution and direct source link remain visible on reveal. USGS source
records, rather than model predictions, determine the documented origin.
