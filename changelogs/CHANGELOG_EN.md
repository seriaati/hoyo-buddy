# Hoyo Buddy Changelog

## v1.15.4

### New Features

- (`/build genshin`) Show information about the synergies of a character.
- (`/mimo`) Added a new command to manage Traveling Mimo.

### Improvements

- (`/build genshin`) Improved the card designs.
- (`/notes`) Use the event calendar API to check for planar fissure events.

### Bug Fixes

- (`/build genshin`) Fixed some UI issues.
- (`/events`) Fixed some issues causing the command to be inaccessible.
- (`/gacha-log upload`) Fixed `ValidationError` with UIGF data.
- (`/gacha-log upload`) Fixed `KeyError` with UIGF versions older than 3.0.
- (`/search`) Fixed duplicated autocomplete choices.

## v1.15.3

Bad code in the previous versions caused some users to see the "too many requests" error while logging in, please see
[this article](https://link.seria.moe/kky283) for more information.

### New Features

- (`/profile zzz`) Added a selector to select substats that you want to highlight.
- (`/profile hsr`) Added Fugue and Sunday card data.

### Improvements

- (`/redeem`) Mask redeem code links with the code itself.
- (`/challenge genshin theater`, `/challenge genshin abyss`) Show traveler's element in the cards.
- (`/accounts`) Show custom error message for "Too many requests" error.

### Bug Fixes

- Fixed an issue where commands are not being translated to other languages.
- Fixed an issue where timed out modals are not being closed properly.
- Fixed API retry logic and error handling logic.
- Fixed `ValueError` in some commands.
- Fixed modal timeout time being too short.
- Handle `KeyError` in web server redirect endpoint.
- (`/profile`) Handle `EnkaAPIError` when fetching data from Enka Network API.
- (`/profile`) Handle Enka Network API gateway timeout errors gracefully.
- (`/profile`) Fixed `BadRequestError` when generating AI images.
- (`/upload`) Fixed `BadRequestError` when uploading images.

## v1.15.2 and below

Previous changelogs were written in the #updates channel in our [Discord server](https://link.seria.moe/hb-dc).
