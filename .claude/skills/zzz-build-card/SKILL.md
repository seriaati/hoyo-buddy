---
name: zzz-build-card
description: Design ZZZ build card data (hoyo-buddy-assets/assets/zzz-build-card/agent_data.yaml for template 1, agent_data_temp2.yaml for template 2) for new or existing Zenless Zone Zero agents and their skins, by rendering variants with scripts/zzz_card_variants.py for maintainers to choose from. Use when asked to design, add or update a ZZZ agent's build card, its accent color, image position or level text position.
---

# ZZZ build card design

Card data is designed by rendering variants through the real `ZZZAgentCard` drawer with `scripts/zzz_card_variants.py`, then letting a maintainer pick one per card. Read the script's module docstring for the full command reference. All commands run from the repo root.

## Workflow

1. **Init**: `uv run scripts/zzz_card_variants.py init <agent_id>`
   - Pulls the agent's art from nanoka (latest version from `https://static.nanoka.cc/manifest.json`) and writes `scripts/output/zzz_variants/<agent_id>/variants.yaml` (gitignored).
   - Creates one card per art: `t1_<id>` (default art), `t1_<id>_<skin_id>` (each skin), and `t2_<id>` (M6 cinema art). Template 2 is skipped until nanoka publishes `Mindscape_<id>_3`. Tell the user and come back to it later.
   - Each card's `base` starts from the key's existing entry, or from the latest agent's entry rescaled to the new art. Treat it as a starting point only.
   - `palette` lists colors extracted from the art. It picks up skin tones, so pick colors by looking at the art too.
2. **Look at the art** before designing. Note the main colors, how busy the art is (weapons, wings, flowing coats), and where the head sits.
3. **Design**: edit `base` and add 3–4 named `variants` per card that override `base` keys. Vary color and, where it makes sense, layout (image size, level position, `zzz_text`). If a variant overrides only one of `image_w`/`image_h`, the other is derived from the art's aspect ratio.
4. **Render**: `uv run scripts/zzz_card_variants.py render <agent_id> [card_id ...]`. Look at each contact sheet (`scripts/output/zzz_variants/<agent_id>/<card_id>.png`) and fix problems before showing anything. Iterate as many times as needed.
5. **Present** the contact sheets with a short table of variants and your recommendation, then **let the maintainer choose**. Never apply without their pick.
6. **Apply**: `uv run scripts/zzz_card_variants.py apply <agent_id> <card_id> <variant>` for each pick. Then verify the bot can load the data:
   ```
   uv run python -c "import asyncio; from hoyo_buddy.draw.card_data import CARD_DATA; asyncio.run(CARD_DATA.load()); print(CARD_DATA.zzz['<key>'])"
   ```

## Design rules

- **Skins are separate agents.** Each skin card gets its own color, image size/position, level position and `zzz_text`, chosen for that art. Don't copy the default skin's layout or offer the default's color for a skin. Skins usually have different colors from the default.
- **Center the visual focus.** The head/torso should sit in the middle of the open area between the left equip panel (~x 960) and the right stats panel (~x 2685), around x 1820, not pushed right. The render label's `focus x` is an alpha-weighted head/shoulder position. Long hair, tails or capes flowing to one side skew it (e.g. it can read ~1960 for an art that looks centered), so confirm visually.
- **Colors**: accessible (text stays readable) and comfortable: low-saturation, pastel-like versions of the agent's main colors. Avoid bright red, yellow or highly saturated colors, unless the agent really is that vibrant. Offer colors from different parts of the design (hair, outfit, weapon) as separate variants.
- **`zzz_text`** (the background "ZENLESS" text, top-left): hide it when the foreground is busy, or when the level text would overlap it. It's free to show when the art is calm and the level text sits elsewhere (e.g. lower-left).
- **Level text position**: balance not covering the agent much against not sitting in odd spots (the very side or the dead center). Common spots are top-left next to the equip panel (~900, 60) and lower-left (~960, 780). The "Lv.60" text is ~630 px wide and the disc panel limits how far left it can go. Make sure the rank ("M6") below it stays inside the card (card height is 1286). `level_flip` right-aligns the rank under the level text.
- **`level_stroke`** (white outline): only when the level text actually overlaps the character art. Over the plain white or color-blob background it should be off. Use the render label (`art under Lv …%, under rank …%`). It suggests `(turn stroke ON)` or `(stroke not needed)`.
- **Image size**: full-body arts usually look right with `image_h` around 2500–3100. Show the face clearly and don't crop the top of the head.
- **Template 2 (M6 cinema art) is sized by its solid art, not the image size.** These images have transparent strips (often 90–120 px on a 1080 px image) above and below the art, and the bottom edge can be a soft fade or a slanted cut. For a new agent, `init` already fits the `base` image this way: solid art's top and bottom slightly overshoot the card's edges, centered at x 1700. Keep that size and only nudge `image_x` a little left or right. Keep the image centered even if the face isn't. Then run `holes <agent_id> t2_<id> [variant]` to find level text positions with the least art under them. Use a 0% spot with `level_stroke` off if there is one; otherwise overlap the art with `level_stroke` on. Re-run `holes` after nudging the image, since the holes move with it. Check the full-size render for thin pale strips along the top and bottom edges.
- **Template 2: the face must be visible.** If centering leaves the face against or under a panel (e.g. the left equip/disc panel), nudge the image further until the face is clear, even if the art ends up off-center. Re-run `holes` at each position, since nudging can open new spots (e.g. top-left).
- **Template 2 color**: if the M6 art's color scheme is similar to the standing art, reuse the template 1 color by leaving `color` out of the template 2 variants (the entry then has no `color` and the bot falls back to template 1's). Only offer a different color when the M6 art's palette clearly differs.
- **Don't flip** (`flip: false`). Art is drawn from a specific perspective and looks wrong mirrored.

## Gotchas

- `init --force` overwrites the whole variants file, including your variants. Never run it on a file you've edited unless that's intended.
- nanoka shows `...` for unreleased text (full names, skin names). `init` falls back to the short name for the full name, and skin labels become `<Name>: ...`. That label is what `apply` writes as the entry's comment, so edit `label` in the variants file if the real name is known.
- Template 2 entries may omit `color`. The bot (and `render`) fall back to the template 1 color of the same agent.
- Cards render with a stored sample agent (`scripts/data/zzz_sample_agent.json`), so Enka isn't needed. Refresh it with `fetch-sample [--uid UID]` only if it breaks.
- Don't commit or push unless the user asks. The data files live in the `hoyo-buddy-assets` submodule.
