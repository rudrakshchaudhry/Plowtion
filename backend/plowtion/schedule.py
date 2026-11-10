"""Rule-based planting / harvest schedule generation.

Durations are approximate, general-purpose figures (they match the ranges shown on
the frontend crop guide). They are not tuned to a specific region or variety.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


@dataclass(frozen=True)
class CropCalendar:
    days_min: int
    days_max: int
    # Event the schedule is anchored on: "planting" for annual crops, or the start
    # of the fruiting cycle ("flowering", "pruning") for established perennials.
    anchor: str = "planting"


CROP_CALENDAR: dict[str, CropCalendar] = {
    "rice": CropCalendar(90, 150),
    "maize": CropCalendar(70, 100),
    "chickpea": CropCalendar(95, 120),
    "kidneybeans": CropCalendar(85, 95),
    "pigeonpeas": CropCalendar(120, 180),
    "mothbeans": CropCalendar(75, 90),
    "mungbean": CropCalendar(60, 75),
    "blackgram": CropCalendar(90, 120),
    "lentil": CropCalendar(120, 150),
    "watermelon": CropCalendar(70, 100),
    "muskmelon": CropCalendar(65, 90),
    "cotton": CropCalendar(150, 180),
    "jute": CropCalendar(120, 150),
    "banana": CropCalendar(300, 365),
    "papaya": CropCalendar(240, 300),
    "pomegranate": CropCalendar(180, 210, "flowering"),
    "mango": CropCalendar(120, 150, "flowering"),
    "grapes": CropCalendar(90, 120, "pruning"),
    "apple": CropCalendar(130, 150, "flowering"),
    "orange": CropCalendar(210, 240, "flowering"),
    "coconut": CropCalendar(330, 365, "flowering"),
    "coffee": CropCalendar(180, 240, "flowering"),
}

SUPPORTED_CROPS = sorted(CROP_CALENDAR)


class UnknownCrop(ValueError):
    pass


def normalize_crop(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise UnknownCrop("crop is required")
    key = name.strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    if key not in CROP_CALENDAR:
        raise UnknownCrop(f"unsupported crop '{name}'; supported: {', '.join(SUPPORTED_CROPS)}")
    return key


def _stage(name: str, start: date, end: date, tasks: list[str]) -> dict[str, Any]:
    return {"stage": name, "start": start.isoformat(), "end": end.isoformat(), "tasks": tasks}


def generate_schedule(crop: str, start: date, profile: dict[str, dict[str, float]] | None = None) -> dict[str, Any]:
    """Build a stage-by-stage schedule for ``crop`` anchored at ``start``."""
    key = normalize_crop(crop)
    cal = CROP_CALENDAR[key]
    day = lambda n: start + timedelta(days=n)  # noqa: E731

    establish_end = max(14, round(cal.days_min * 0.2))
    growth_end = round(cal.days_min * 0.6)

    water_hint = ""
    if profile and "rainfall" in profile:
        rain = profile["rainfall"]
        water_hint = f" Typical rainfall for {key} in the training data: {rain['min']:.0f}-{rain['max']:.0f} mm."

    if cal.anchor == "planting":
        prep_tasks = [
            "Test soil N, P, K and pH; amend toward the crop's preferred range.",
            "Clear residue, till or loosen the bed, and incorporate compost.",
        ]
        anchor_tasks = [f"Plant {key} (seed or transplant) and water in thoroughly."]
        establish_tasks = ["Check germination / establishment and fill gaps.", "Control weeds early."]
    else:
        prep_tasks = [
            "Test soil and apply a balanced fertilizer before the fruiting cycle.",
            "Inspect trees or vines; remove dead or diseased wood.",
        ]
        anchor_tasks = [f"Start of the {cal.anchor} stage for established {key} plants."]
        establish_tasks = ["Monitor fruit set; thin if overloaded.", "Control weeds around the root zone."]

    stages = [
        _stage("Preparation", day(-14), day(-1), prep_tasks),
        _stage(cal.anchor.capitalize(), day(0), day(0), anchor_tasks),
        _stage("Establishment", day(1), day(establish_end), establish_tasks),
        _stage(
            "Growth",
            day(establish_end + 1),
            day(growth_end),
            ["Irrigate according to soil moisture." + water_hint, "Scout weekly for pests and disease.", "Side-dress nitrogen if leaves yellow."],
        ),
        _stage(
            "Flowering and fruit development",
            day(growth_end + 1),
            day(cal.days_min - 1),
            ["Keep moisture steady; avoid water stress.", "Continue pest and disease monitoring."],
        ),
        _stage(
            "Harvest window",
            day(cal.days_min),
            day(cal.days_max),
            ["Harvest at maturity; check a sample before harvesting the full crop.", "Dry, cool or store produce promptly."],
        ),
    ]

    return {
        "crop": key,
        "anchor": cal.anchor,
        "anchor_date": start.isoformat(),
        "harvest_start": day(cal.days_min).isoformat(),
        "harvest_end": day(cal.days_max).isoformat(),
        "stages": stages,
        "note": "Approximate, rule-based schedule; adjust for local climate and variety.",
    }


def schedule_to_text(schedule: dict[str, Any]) -> str:
    lines = []
    for stage in schedule["stages"]:
        span = stage["start"] if stage["start"] == stage["end"] else f"{stage['start']} to {stage['end']}"
        lines.append(f"{stage['stage']} ({span}):")
        lines.extend(f"  - {task}" for task in stage["tasks"])
    lines.append(schedule["note"])
    return "\n".join(lines)
