from __future__ import annotations

from .schemas import MissionInterpretation, NeedPlan


class NeedPlannerAgent:
    """Turns an extracted mission into transparent, deterministic category needs."""

    _BUILD_SETUP = {
        "gaming": (["gaming laptop or desktop", "keyboard", "mouse", "headset"], ["mousepad", "desk", "chair", "speakers", "webcam"]),
        "workspace": (["laptop or desktop", "keyboard", "mouse"], ["monitor", "desk lamp", "webcam", "headset"]),
    }

    def plan(self, mission: MissionInterpretation) -> NeedPlan:
        goal = mission.goal.lower()
        mission_type = mission.mission_type.lower()
        required: list[str] = []
        optional: list[str] = []
        if mission_type == "build_setup" or "setup" in goal:
            for keyword, categories in self._BUILD_SETUP.items():
                if keyword in goal:
                    required, optional = categories
                    break
            if not required:
                required = ["primary device", "keyboard", "mouse"]
                optional = ["headset", "desk accessories"]
        elif "travel" in goal:
            required, optional = ["travel bag", "power adapter"], ["power bank", "packing accessories", "umbrella"]
        elif "home" in goal or "apartment" in goal:
            required, optional = ["core home essentials"], ["storage", "lighting", "cleaning supplies"]
        else:
            required, optional = [mission.goal], []

        owned = {item.lower() for item in mission.owned_items}
        required = [category for category in required if category.lower() not in owned]
        optional = [category for category in optional if category.lower() not in owned]
        return NeedPlan(required_categories=required, optional_categories=optional)
