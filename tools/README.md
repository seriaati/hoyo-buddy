# Tools

Internal utility scripts for maintaining the Hoyo Buddy codebase.

## cleanup_l10n.py

**Purpose:** Scans the codebase for used localization keys and removes unused keys from `l10n/en_US.yaml`.

**How it works:**

- Parses all Python files in the repository
- Detects keys referenced via `LocaleStr(key="...")` (excluding `mi18n_game`/`data_game` usages)
- Detects keys from `app_commands.locale_str(..., key="...")`
- **Detects string literals that match YAML keys** (e.g., `"hsr.ultimate"` in dicts/tuples)
- **Detects f-string patterns and preserves matching keys**:
  - Dot-separated: `f"characters.sorter.{var}"` → preserves `characters.sorter.*`
  - Underscore patterns: `f"shiyu_{floor.index}_frontier"` → preserves `shiyu_*_frontier`
- Preserves keys used by helper classes:
  - `EnumStr` → all StrEnum values from `hoyo_buddy/enums.py`
  - `WeekdayStr` → monday, tuesday, wednesday, thursday, friday, saturday, sunday
  - `LevelStr`, `TimeRemainingStr`, `UnlocksInStr`, `RarityStr` → their respective keys
- Preserves keys starting with `dyk_` (used by `Translator.get_dyks()`)

**Usage:**

Dry run (default, shows unused keys without modifying files):

```bash
uv run python tools/cleanup_l10n.py
```

Write changes (creates a `.bak` backup first):

```bash
uv run python tools/cleanup_l10n.py --write
```

**Options:**

- `--root <path>` — Repository root to scan (default: auto-detected)
- `--yaml <path>` — Path to en_US.yaml (default: `l10n/en_US.yaml`)
- `--write` — Apply removals (otherwise dry-run)
- `--exclude-tests` — Skip scanning test files

**Example output:**

```text
en_US keys: 772 | used (detected): 802 | unused (candidates): 0
No unused keys detected.
```

**Safety:**

- Always run without `--write` first to review changes
- Backup file (`en_US.yaml.bak`) is created automatically
- Preserves insertion order of keys in YAML
