"""Animated custom images, converted from sponsors' uploads and framed in build cards' image masks."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import av
from av.error import FFmpegError
from PIL import Image, ImageSequence, UnidentifiedImageError

from hoyo_buddy.constants import (
    ANIMATED_CARD_SCALE,
    ANIMATED_CUSTOM_IMAGE_MAX_DURATION,
    ANIMATED_CUSTOM_IMAGE_MAX_FPS,
    ANIMATED_CUSTOM_IMAGE_MAX_SIDE,
    ANIMATED_CUSTOM_IMAGE_QUALITY,
)
from hoyo_buddy.draw.drawer import Drawer

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

__all__ = ("convert_animation", "frame_animation", "is_animated")

FRAMED_QUALITY = 90
"""WEBP quality of animations framed for a card, re-encoded once more when the card is drawn."""


def is_animated(data: bytes) -> bool:
    """Whether the upload is an animated image or a video, which Pillow can't open."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            return getattr(im, "is_animated", False)
    except UnidentifiedImageError:
        return True


type Frame = Image.Image | av.VideoFrame
"""A decoded frame, video frames are converted once they're known to be kept."""


def _decode_image(im: Image.Image) -> Iterator[tuple[Frame, float, float]]:
    start = 0.0
    for frame in ImageSequence.Iterator(im):
        # Converted first since WEBP frames get their duration when loaded
        rgba = frame.convert("RGBA")
        # Browsers show GIF frames of 10ms or less for 100ms
        duration = frame.info.get("duration") or 0
        duration = (duration if duration > 10 else 100) / 1000
        yield rgba, start, duration
        start += duration


def _decode_video(data: bytes) -> Iterator[tuple[Frame, float, float]]:
    with av.open(io.BytesIO(data), mode="r") as container:
        if not container.streams.video:
            msg = "The upload has no video stream"
            raise ValueError(msg)

        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        rate = stream.average_rate or stream.guessed_rate or ANIMATED_CUSTOM_IMAGE_MAX_FPS
        for frame in container.decode(stream):
            if frame.pts is not None:
                yield frame, frame.time, float(1 / rate)


def _decode(data: bytes) -> Iterator[tuple[Frame, float, float]]:
    """Decode the upload's frames with their start times and durations in seconds."""
    try:
        im = Image.open(io.BytesIO(data))
    except UnidentifiedImageError:
        try:
            yield from _decode_video(data)
        except FFmpegError as e:
            msg = "The upload isn't an image or a video"
            raise ValueError(msg) from e
        return

    with im:
        yield from _decode_image(im)


def _resample(frames: Iterable[tuple[Frame, float, float]]) -> Iterator[tuple[Frame, int]]:
    """Cut frames to the max duration and drop frames over the max frame rate.

    Yields:
        The frames and their durations in ms.
    """
    interval = 1 / ANIMATED_CUSTOM_IMAGE_MAX_FPS
    pending: tuple[Frame, int] | None = None
    next_start = 0.0
    end = 0.0

    for frame, start, duration in frames:
        if start >= ANIMATED_CUSTOM_IMAGE_MAX_DURATION:
            break
        end = min(start + duration, ANIMATED_CUSTOM_IMAGE_MAX_DURATION)
        # Tolerate float error between frames exactly an interval apart
        if start < next_start - 1e-3:
            continue

        # Durations from rounded timestamps, so they don't drift from the source's
        start_ms = round(start * 1000)
        if pending is not None:
            yield pending[0], start_ms - pending[1]
        pending = (frame, start_ms)
        next_start = start + interval

    if pending is not None:
        yield pending[0], max(round(end * 1000) - pending[1], 1)


def _to_image(frame: Frame) -> Image.Image:
    """Convert a frame to RGBA, scaled down to the max side."""
    width, height = (frame.width, frame.height)
    scale = min(ANIMATED_CUSTOM_IMAGE_MAX_SIDE / max(width, height), 1)
    size = (round(width * scale), round(height * scale))

    if isinstance(frame, av.VideoFrame):
        return frame.reformat(*size, format="rgba", interpolation="LANCZOS").to_image()
    if size == frame.size:
        return frame
    return frame.resize(size, Image.Resampling.LANCZOS)


def convert_animation(data: bytes) -> bytes:
    """Convert an uploaded GIF, animated WEBP or video to an animated WEBP within the caps.

    Raises:
        ValueError: The upload isn't an animated image or a video.
    """
    frames = ((_to_image(frame), duration) for frame, duration in _resample(_decode(data)))
    first = next(frames, None)
    if first is None:
        msg = "The upload has no frames"
        raise ValueError(msg)

    def all_frames() -> Iterator[tuple[Image.Image, int]]:
        yield first
        yield from frames

    result = Drawer.save_animated(
        all_frames(), first[0].size, quality=ANIMATED_CUSTOM_IMAGE_QUALITY
    )
    return result.getvalue()


def frame_animation(
    source: Path, mask: Path, *, zoom: int, focus: tuple[int, int]
) -> tuple[Path, tuple[int, int]]:
    """Scale and crop an animated custom image to a card's image mask, like the pre-rendered
    animations in spine.yaml, see Drawer.draw_animated_card. Cached next to the source.

    The animation covers the mask at a zoom of 100, and focus is where it sits in the mask in
    percent, like CSS's object-position.

    Args:
        source: Path of the animated custom image.
        mask: Path of the card's image mask.
        zoom: Zoom in percent.
        focus: Horizontal and vertical position in percent.

    Returns:
        The framed animation's path and its uncropped top-left in the mask.
    """
    with Image.open(mask) as im:
        area = im.size
    with Image.open(source) as im:
        source_size = im.size

    scale = max(area[0] / source_size[0], area[1] / source_size[1]) * zoom / 100
    width, height = round(source_size[0] * scale), round(source_size[1] * scale)
    x = round((area[0] - width) * focus[0] / 100)
    y = round((area[1] - height) * focus[1] / 100)

    path = source.with_name(
        f"{source.stem}_{area[0]}x{area[1]}_{zoom}_{focus[0]}_{focus[1]}{source.suffix}"
    )
    if path.exists():
        return path, (x, y)

    left, top = max(0, -x), max(0, -y)
    right, bottom = min(width, area[0] - x), min(height, area[1] - y)
    box = (
        left / scale,
        top / scale,
        min(right / scale, source_size[0]),
        min(bottom / scale, source_size[1]),
    )
    size = (
        round((right - left) * ANIMATED_CARD_SCALE),
        round((bottom - top) * ANIMATED_CARD_SCALE),
    )

    def frames() -> Iterator[tuple[Image.Image, int]]:
        with Image.open(source) as im:
            for frame in ImageSequence.Iterator(im):
                resized = frame.convert("RGBA").resize(size, Image.Resampling.LANCZOS, box=box)
                yield resized, frame.info["duration"]

    data = Drawer.save_animated(frames(), size, quality=FRAMED_QUALITY)
    # Written to a temporary file first, since other workers may be framing it too
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as f:
        f.write(data.getbuffer())
    Path(f.name).replace(path)
    return path, (x, y)
