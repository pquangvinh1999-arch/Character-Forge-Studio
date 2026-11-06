# Third-Party Licenses, Notices, and Source Attribution

Character Forge Studio integrates selected capabilities and reference patterns from three open-source upstream repositories pinned in `vendor/` and recorded in `vendor/VENDOR_LOCK.json`. Original upstream sources remain unmodified in `vendor/`.

---

## 1. agent-sprite-forge

- **Upstream Repository**: https://github.com/0x0funky/agent-sprite-forge
- **Pinned Commit**: `72fa5ad92d79b811acff464da32c8f3b1caa010f` (v0.4.0, 2026-11-06)
- **License**: MIT License
- **Copyright**: Copyright (c) 2026 0x0funky
- **License File**: `vendor/agent-sprite-forge/LICENSE`

```text
MIT License

Copyright (c) 2026 0x0funky

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 2. sprite-gen

- **Upstream Repository**: https://github.com/aldegad/sprite-gen
- **Pinned Commit**: `4f5ccd55c7cf06685a41f954acc1e476b7772ece` (v3.15.0, 2026-11-02)
- **License**: Apache License, Version 2.0
- **Copyright**: Copyright 2026 Alex Kim
- **License File**: `vendor/sprite-gen/LICENSE`
- **Notice File**: `vendor/sprite-gen/NOTICE`

### Preserved Upstream NOTICE (`vendor/sprite-gen/NOTICE`)

```text
sprite-gen
Copyright 2026 Alex Kim

This project is inspired by the Apache-2.0 licensed hatch-pet component-row
workflow. sprite-gen targets generic game sprite atlases and does not include
Codex pet assets, pet packages, or hatch-pet visual assets.

The `align_x: "alpha-centroid"` frame alignment (sprite_gen/extract.py) is a
port of the alpha-weighted mass-centroid alignment from perfectpixel-studio
(https://github.com/gykim80/perfectpixel-studio, internal/sprite/extract.go),
Copyright Andrew Kim (gykim80), MIT License.

The `segmentation: "projection"` frame separation (sprite_gen/segment.py) is a
port of the projection-profile + DP optimal-cut segmentation from
perfectpixel-studio (https://github.com/gykim80/perfectpixel-studio,
internal/sprite/segment.go), Copyright Andrew Kim (gykim80), MIT License.

The opt-in `chroma.mode: "ycbcr"` background matting (sprite_gen/extract.py) is
a port of the chrominance-plane matting — CbCr border-mode key detection,
Hermite soft matte, key-direction despill, border flood fill and the pure-key
rematte self-diagnostic — from perfectpixel-studio
(https://github.com/gykim80/perfectpixel-studio, internal/sprite/chroma.go),
Copyright Andrew Kim (gykim80), MIT License.

The estimation-only `estimate_pixel_grid_runlen` pitch estimator
(sprite_gen/extract.py) is a port of the unfake same-color run-length mode
block-size estimation from perfectpixel-studio
(https://github.com/gykim80/perfectpixel-studio, internal/sprite/pixelize.go),
Copyright Andrew Kim (gykim80), MIT License.

RIFE's torch backend (sprite_gen/video/rife_torch.py) writes again the IFNet of
rife-v4.6 — its structure and parameter names, and its warp — from Practical-RIFE
(https://github.com/hzwer/Practical-RIFE, commit f6b5132, train_log/IFNet_HDv3.py
and model/warplayer.py), Copyright (c) 2021 hzwer, MIT License.

It writes again the IFNet of rife-v4.25 — its encoder and five blocks, their
structure and parameter names — from Practical-RIFE's 4.25 model
(https://github.com/hzwer/Practical-RIFE, the v4.25 train_log of 2024-09-19,
train_log/IFNet_HDv3.py), Copyright (c) 2021 hzwer, MIT License. Practical-RIFE's
README: "The content of these links is under the same MIT license as this
project." The 4.25 weights it runs are that model's published flownet.pkl
(sha256 6615790efd627772917205db291f51cd392528a157ecbb2ecaeec3bff8eb6de2) as
TNTwise's rife-ncnn-vulkan converts them, read from the release zip.

Its test-time augmentation — the pair turned eight ways and run both ways in time,
the flows averaged at every level — follows rife-ncnn-vulkan 20221029
(https://github.com/nihui/rife-ncnn-vulkan, src/rife.cpp RIFE::process_v4 and its
rife_*_tta shaders), Copyright (c) 2020 nihui, MIT License.

`sprite-gen rife install` downloads TNTwise's fork of rife-ncnn-vulkan, release
20250112 (https://github.com/TNTwise/rife-ncnn-vulkan), Copyright (c) 2020 nihui,
MIT License, its LICENSE kept in the install: the binary, which sprite-gen runs
as an external tool, and its rife-v4.25 and rife-v4.6 models (Practical-RIFE's
weights, MIT, as above), which both backends read. sprite-gen ships none of them.
```

---

## 3. Claude-Code-Game-Studios

- **Upstream Repository**: https://github.com/Donchitos/Claude-Code-Game-Studios
- **Pinned Commit**: `05ad7c8a5b8aa2aa86bbd3439ae7cf7295cac418` (v1.2.0, 2026-10-19)
- **License**: MIT License
- **Copyright**: Copyright (c) 2026 Donchitos
- **License File**: `vendor/Claude-Code-Game-Studios/LICENSE`

```text
MIT License

Copyright (c) 2026 Donchitos

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
