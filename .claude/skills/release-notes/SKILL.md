---
name: release-notes
description: Draft Hoyo Buddy's Discord release notes for a new version as Roler markup (the maintainer's Components V2 bot, docs at https://seria.is-a.dev/roler/), from the commits since the last tag. Recommends the version number, writes the messages in the established style with screenshot placeholders, and keeps each message under Discord's 4000-character and 40-component limits with scripts/count_roler_components.py. Use when asked to write, draft or update release notes, a release announcement or an update post for a Hoyo Buddy version, or to pick the next version number.
---

# Release notes

Release notes are posted in the Hoyo Buddy Discord server through Roler, as one or more consecutive messages from the same webhook identity so they read as one post. Buttons can open extra Roler templates as ephemeral panels. `references/v1.17.0.md` is the first release written this way. Read it before drafting.

Save drafts in `scripts/output/release-notes/<version>/` (gitignored), not the session scratchpad, which can be wiped between sessions. Commands run from the repo root.

## 1. Pick the version

```bash
git describe --tags --abbrev=0
git log $(git describe --tags --abbrev=0)..HEAD --no-merges --reverse --format='=== %h %s%n%b'
```

Recommend a version from the commits:

- **Minor** (`v1.18.0`): any user-facing `feat`, or a breaking change (`feat!`, `BREAKING CHANGE`, a removed or renamed command).
- **Patch** (`v1.17.1`): only fixes and small tweaks. The v1.16.x series went up to .24 this way.

## 2. Find what's already announced

Previous release notes are sometimes written after the tag, so they can already cover commits after it (the v1.17.0 notes announced `/sponsor` and the Lucy skin, which came after the `v1.17.0` tag). Ask the user for the previous notes, or which items they announced, and leave those out.

## 3. Gather details

Don't describe a feature from its commit subject alone. Check:

- **Commit bodies:** limits, defaults, sponsor-only gating, migrations that reset user choices.
- **The `l10n/en_US.yaml` diff** (`git diff <tag>..HEAD -- l10n/en_US.yaml`) for exact setting, button and option names. Quote the names users will see.
- **The code**, when a commit doesn't say where a setting lives, which games or templates it covers, or what free users get compared to sponsors (`is_supporter` checks).
- **Linked pages** (website, docs) by fetching them. Flag pages that don't exist yet; a new page can serve the homepage until it's deployed.

Leave out internal work: CI, logging, Sentry, refactors, translation chores, asset bumps, and fixes to features that are new in this release. Group the rest into notable features (own sections), sponsor perks, and other changes. Fixes go in one Miscellaneous list, ending with "Many other bug fixes." when there are more.

## 4. Write the messages

Follow `references/v1.17.0.md`:

- **First message:** the `[webhook name=Seria avatar=https://iili.io/neBMOsS.png]` line, `# vX.Y.Z Release Notes :tada:`, a short intro starting with "Haelo" that pings the update role `<@&1042426904977870888>`, then `-# This message is written using [Roler](<https://roler.seria.moe>), you can configure pings in <#1488178624170426570>`.
- **Sections:** `---`, then `## Title`, the screenshot, then the text. Invisible small separators (`[separator size=small visible=false]`) add space around images and buttons. Mark sponsor-only features "(Sponsors)" in the heading and mention `/sponsor`.
- **Last section:** `## Release Notes` with the docs links (English, 繁體中文, 简体中文, Tiếng Việt, Español), at `https://docs.hb.seria.moe/<lang>/release-notes/` with `en`, `zh-tw`, `zh-cn`, `vi` and `es`. Check the paths still exist.
- **Images:** `[image url=TODO-<short-name>]` placeholders for the user to replace with screenshots. Two or more images can go in one `[gallery]`.
- **Voice:** the maintainer's, casual and first person ("Haelo", "let me know"). Short, plain sentences. Say what changed and where to find it; no hype.

Write sections inline in the messages. Use `[button template=<id>]` panels only for per-game views, with the game emojis:

```
[button template=gi-<feature> emoji=:GI_CIRCLE:1562968237765828699 color=grey][/button]
[button template=hsr-<feature> emoji=:HSR_CIRCLE:1562968239783415809 color=grey][/button]
[button template=zzz-<feature> emoji=:ZZZ_CIRCLE:1562968241540829195 color=grey][/button]
```

A template file starts with `[template id=<id>]`. Name release-specific template IDs `vX-Y-Z-<name>`.

Number the files in posting order: `1-message1.txt`, `2-message2.txt`, …, then the button templates.

## 5. Fit Discord's limits

Each message must stay within **4000 characters** (Nitro) and **40 components**. Roler makes every blank-line-separated paragraph, heading, image, gallery, separator, action row and button its own component, so the component limit is usually hit first.

```bash
uv run scripts/count_roler_components.py scripts/output/release-notes/<version>/*.txt
```

Keep the established style and split into more messages instead of cramming one. Split at a section boundary. Every message after the first starts with the same `[webhook ...]` line followed by `---`, and the message before it doesn't end with `---`. Aim for about 35 components per message: the count is an estimate, and when Discord rejects a message at a lower count, trust Discord.

## 6. Before the user sends

- Re-run the step 1 log. If commits landed since the draft, update the sections they change (renamed settings, moved buttons, reset defaults) and re-count.
- List the `TODO-` image placeholders still left.
- Don't overwrite the user's edits (image URLs, added lines). Read the files again before changing them.
