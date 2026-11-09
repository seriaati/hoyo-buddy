---
name: hsr-build-card
description: Design HSR build card data for new or existing Honkai Star Rail characters. Picks the card color (`primary`, plus `primary-dark` when the automatic dark mode conversion looks wrong) in hoyo-buddy-assets/assets/hsr-build-card/data.yaml by rendering light/dark contact sheets with scripts/gen_hsr_build_card.py, and reviews the animated (Spine) image's zoom and position for both templates with scripts/hsr_spine_framing.py. Use when asked to add, design or update an HSR character's build card, its color or dark mode color, or to check/fix an HSR animated card's framing, especially after a new character releases.
---

# HSR build card design

An HSR card needs much less than a ZZZ one. The art (`https://static.nanoka.cc/assets/hsr/avatardrawcardresult/<id>.webp`) and layout are fixed, so a new character needs:

1. **A color** in `hoyo-buddy-assets/assets/hsr-build-card/data.yaml`: `primary`, plus `primary-dark` only when the automatic dark mode conversion looks wrong. Only template 1 uses it; template 2 is grey.
2. **A check of the animated image's framing** (supporters' animated cards) in each template's `spine.yaml`: same zoom, size and position as the static art.

Without a `data.yaml` entry, the bot raises `NoCardDataError` for the character. All commands run from the repo root.

## Find characters without card data

```
uv run python - <<'EOF'
import json, re, urllib.request, yaml
get = lambda u: json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "hoyo-buddy"})))
v = get("https://static.nanoka.cc/manifest.json")["hsr"]["latest"]
chars = get(f"https://static.nanoka.cc/hsr/{v}/character.json")
spines = get("https://static.nanoka.cc/assets/hsr/spine/manifest.json")
data = yaml.safe_load(open("hoyo-buddy-assets/assets/hsr-build-card/data.yaml"))
for k, c in chars.items():
    if k not in data:
        print(k, re.sub(r"<[^>]+>", "", c.get("en", "")), "(spine)" if k in spines else "(no spine)")
EOF
```

## Color workflow

1. **Look at the art.** Download the character's art (URL above) into the scratchpad and view it. Note the main colors of the hair, outfit and weapon, and the art's background. If nanoka doesn't have it yet, find the art elsewhere and pass `--image-url` in the next steps.
2. **Pick 3–4 candidate colors** from different parts of the design (see the rules below).
3. **Render**:
   ```
   uv run scripts/gen_hsr_build_card.py --char-id <id> --both --color '#aaaaaa' '#bbbbbb' ...
   ```
   This writes `scripts/output/hsr_build_card_sheet.png`, with one row per color and light mode next to dark mode. The cards use a stored enka showcase character (Firefly) with the new character's art, so ignore the name and stats.
4. **Check the dark column.** By default it shows the automatic conversion (`dark (auto)`). If it looks wrong (see below), add `/DARK_HEX` candidates, e.g. `'#a12d35/#b86369'`, and re-render. Iterate until each option looks right in both modes before showing anything.
5. **Present** the contact sheet with a short table of the options and your recommendation, then **let the maintainer choose**. Never write to `data.yaml` without their pick.
6. **Apply**: add the entry to `data.yaml` in ID order (8xxx Trailblazer entries stay last). New entries have no `arts`:
   ```yaml
   "1511":
     # Name
     primary: "#a15168"
     primary-dark: "#c07a8e"  # only when chosen
   ```
   Verify the bot loads it:
   ```
   uv run python -c "import asyncio; from hoyo_buddy.draw.card_data import CARD_DATA; asyncio.run(CARD_DATA.load()); print(CARD_DATA.hsr['<id>'])"
   ```

## Color rules

- **Muted, mid-to-dark tones** of the character's main colors, like most existing entries (`#336a76`, `#a15168`, `#647db3`, `#2d5162`). In light mode, `primary` fills the card's outer area and colors the name, level badges and icons on near-white panels, so it has to stay readable there. Very light or pastel colors lose contrast.
- Avoid neon or highly saturated colors (bright red, yellow, green) unless the character really is that vibrant.
- The color should also go with the art's own background, since the art sits right next to the colored area.
- Offer colors from different parts of the design (hair, outfit, weapon) as separate options.

## Dark mode check

In dark mode, the card blends `primary` 88% with a dark grey (`(32, 36, 33)`) for the background and lightens it for text and icons on near-black panels (`_get_colors` in `hoyo_buddy/draw/funcs/hoyo/hsr/build_card.py`). Most colors come out fine. Add a `primary-dark` (same hue, adjusted lightness or saturation) when:

- **The color is very dark**: the background melts into the black panels and the accents get murky. Blade's `#1b2234` uses `primary-dark: "#4a6086"`.
- **The color is saturated**: it glares against the black panels and the accent text looks harsh. Mortenax Blade's `#a12d35` uses `primary-dark: "#b86369"`.
- Text or icons in the accent color are hard to read on the dark panels.

## Animated image (Spine) framing

The weekly `render-spine.yml` GitHub workflow runs `render_hsr_spine.py --new` on Mondays. For each new character it suggests a framing for both templates by overlaying the animation's first frame on the static art, renders and uploads the animation, and records it in `hsr-build-card/spine.yaml` (template 1) and `hsr-build-card2/spine.yaml` (template 2). It sends a comparison to the Discord webhook when the match is poor. Characters with no Spine files on nanoka, or with several skeletons, are skipped and get no animated card.

Review each new character for **both templates** (pass `--template 2` before the subcommand for template 2):

1. `uv run scripts/hsr_spine_framing.py [--template 2] init <id>` writes the suggested framing as `base` to `scripts/output/hsr_spine/hsr{1,2}/variants.yaml` (gitignored). Existing entries are kept unless you pass `--force`.
2. `uv run scripts/hsr_spine_framing.py [--template 2] preview <id>` renders `scripts/output/hsr_spine/hsr{1,2}/<id>-<id>.png`: the static art in the card's art area, next to each variant's first animated frame.
3. Compare them:
   - **Zoom/size**: the character should be the same size as in the static art. If the suggestion zoomed into a small patch of the animation, redo it with `init <id> --force --min-size 0.3` (0.25–0.35).
   - **Position**: the head and body should be where the static art has them, with the face clear and the top of the head not cropped.
   - **Coverage**: no empty strips at the art area's edges, where the animation doesn't reach.
   - **Flip**: it should face the same way as the static art.
4. If it's off, add named `variants` under the character in `variants.yaml` that override `x`, `y`, `height` or `flip`, then preview again. `x`/`y` are the animation bounds' top-left in the art area (negative means it extends past the left or top edge), and `height` is the bounds' height. Raising `height` zooms in around the top-left, so shift `x`/`y` with it to keep the face in place.
5. Show the maintainer the contact sheets when anything needed changing. If the base framing already matches, say so.
6. Apply the picks: `uv run scripts/hsr_spine_framing.py [--template 2] apply <id>[:<variant>]`, then re-render with `uv run scripts/render_hsr_spine.py <id> [--template 2]`. The uploaded animation is cropped to its framing, so every framing change needs a re-render. Rendering needs Node, Chrome (`npm ci --prefix scripts/spine`) and `IMG_UPLOAD_API_KEY` in `.env`. Add `--dry-run` to only write to `scripts/output/spine/`.

If the character isn't in `spine.yaml` yet (the weekly run hasn't happened), `apply` says to render it first: run `uv run scripts/render_hsr_spine.py <id>`, which renders both templates with the suggested framing, then review as above.

## Gotchas

- `init --force` replaces the character's whole entry in `variants.yaml`, including your variants.
- `gen_hsr_build_card.py` without `--color` renders the color already in `data.yaml` (and its `primary-dark` in dark mode). With one color and no `--both`, it writes a single card to `scripts/output/hsr_build_card.png` instead of the sheet.
- The data files live in the `hoyo-buddy-assets` submodule. Don't commit or push unless the user asks.
