# Hoyo Buddy Changelog

## v1.15.6

### New Features

- (`/mimo`) Added support for Genshin's Traveling Mimo (event has already ended by the time of writing).
- (`/mimo`) Added auto prize draw feature.
- (`/challenge zzz`) Added support for the Deadly Assault game mode.
- (`/profile hsr`) Added template 2.
- (`/notes`) Added bounty commission and Ridu weekly points information for ZZZ.

## Improvements

- (`/check-in`) Reduce duplicate check-in API requests.

## Bug Fixes

- (`/mimo`) Fixed notifications being sent when no tasks are completed and no points are claimed.
- (`/mimo`) Fixed how valuable items are being determined.
- (`/mimo`) Handle -510001 error.
- (`/mimo`) Fixed an issue where valuable items are being counted as decorations for HSR.
- (`/mimo`) Disable lottery draw button when the limit is reached.
- (`/challenge zzz`) Fixed wrong bangboo icons in cards.
- (`/events`) Fixed wrong Spiral Abyss progress.
- (`/gacha-log view`) Fixed wrong number of pulls from last rarity.
- Fixed static image folder creation logic.

## v1.15.5

### New Features

- (`/mimo`) Automatically finish tasks that require commenting on a post.
- (`/mimo`) Automatically finish tasks that require following a topic.
- (`/mimo`) Added lottery feature.
- (`/mimo`) Added notification settings.
- (`/profile zzz`) Added an image setting to use Mindscape 3 arts for build cards.
- (`/profile zzz`) Added Harumasa and Miyabi card data.
- (`/search`) Hide "unreleased content" category in certain guilds.

### Improvements

- (`/mimo`) Show task progress for certain tasks.
- (`/mimo`) Show names of completed tasks in the notification.
- (`/mimo`) Improved performance of auto tasks.
- (`/challenge zzz shiyu`) Updated card layout.
- (`/challenge zzz shiyu`) Avoid fetching agent data twice.
- Show Discord server invite link in error embed footers.
- Unset item loading state upon error.
- Added on/off labels to toggle buttons.
- Improved proxy API request logic.
- Improved auto tasks error handling logic.

### Bug Fixes

- (`/mimo`) Added a sleep interval after redeeming a mimo reward gift code.
- (`/mimo`) Fixed tasks missing in task list.
- (`/mimo`) Fixed comment tasks not being completed.
- (`/mimo`) Fixed notifications being sent when no tasks are completed.
- (`/mimo`) Only show HoYoLAB accounts in the account autocomplete.
- (`/mimo`) Fixed `QuerySetError` in auto tasks.
- (`/mimo`) Fixed post comments not being deleted.
- (`/mimo`) Handle cases where Traveling Mimo is not available for a game.
- (`/profile zzz`) Fixed substat highlights not being added to the card.
- (`/profile zzz`) Fixed agents being identified as cached when they are not.
- (`/characters zzz`) Fixed wrong total agent count.
- (`/gacha-log upload`) Fixed issues with zzz.rng.moe imports.
- (`/redeem`) Fixed Miyoushe accounts being shown in account autocomplete.
- (`/build genshin`) Handle missing usage rates for some characters.
- (`/events`) Fixed future HSR warps not being shown as "not available yet".
- Adapt to new ZenlessData keys.
- Fixed issues with Hakushin API.
- Capture general exceptions in `dm_user` method.

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
