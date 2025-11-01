"""Find untranslated strings in locale files and output their English source strings.

Usage:
    python find_untranslated.py zh_CN.yaml
    python find_untranslated.py zh_CN.yaml --output missing_translations.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def load_yaml(file_path: Path) -> dict[str, str]:
    """Load YAML file and return as a flat dictionary."""
    with file_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_empty_translations(translations: dict[str, str]) -> list[str]:
    """Find all keys with empty string translations."""
    return [key for key, value in translations.items() if not value]


def get_english_sources(keys: list[str], en_dict: dict[str, str]) -> dict[str, str]:
    """Get English source strings for the given keys."""
    return {key: en_dict.get(key, "[MISSING IN ENGLISH SOURCE]") for key in keys}


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Find untranslated strings in locale files"
    )
    parser.add_argument(
        "filename",
        help="Locale file name (e.g., zh_CN.yaml)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file name (default: untranslated_<filename>)",
        default=None,
    )

    args = parser.parse_args()

    # Set up paths
    repo_root = Path(__file__).parent.parent
    l10n_dir = repo_root / "l10n"
    locale_file = l10n_dir / args.filename
    en_file = l10n_dir / "en_US.yaml"

    # Validate files exist
    if not locale_file.exists():
        print(f"Error: File not found: {locale_file}")
        return

    if not en_file.exists():
        print(f"Error: English source file not found: {en_file}")
        return

    # Load YAML files
    print(f"Loading {args.filename}...")
    locale_dict = load_yaml(locale_file)

    print("Loading en_US.yaml...")
    en_dict = load_yaml(en_file)

    # Find empty translations
    print("Finding untranslated strings...")
    empty_keys = find_empty_translations(locale_dict)

    if not empty_keys:
        print(f"✓ No untranslated strings found in {args.filename}")
        return

    print(f"Found {len(empty_keys)} untranslated string(s)")

    # Get English sources
    english_sources = get_english_sources(empty_keys, en_dict)

    # Determine output file name
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = repo_root / "tools" / f"untranslated_{args.filename}"

    # Write output
    print(f"Writing results to {output_file}...")
    with output_file.open("w", encoding="utf-8") as f:
        yaml.dump(
            english_sources,
            f,
            allow_unicode=True,
            sort_keys=True,
            default_flow_style=False,
        )

    print(f"✓ Done! Output written to {output_file}")
    print("\nSummary:")
    print(f"  Total untranslated strings: {len(empty_keys)}")
    print(f"  Output file: {output_file}")


if __name__ == "__main__":
    main()
