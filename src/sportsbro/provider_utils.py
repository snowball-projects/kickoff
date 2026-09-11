from __future__ import annotations

from collections import Counter, OrderedDict

from sportsbro.models import CalendarEvent, ProviderOptions
from sportsbro.semantics import include_competition_phase, is_malformed_event


class EventAccumulator:
    def __init__(self, options: ProviderOptions) -> None:
        self.options = options
        self.raw_record_count = 0
        self.duplicate_collisions = 0
        self.malformed_records = 0
        self.dropped_by_phase: Counter[str] = Counter()
        self._events: OrderedDict[str, CalendarEvent] = OrderedDict()

    def add(self, event: CalendarEvent, *, dedupe_key: str | None = None) -> None:
        self.raw_record_count += 1
        if not include_competition_phase(event.competition_phase, self.options):
            self.dropped_by_phase[event.competition_phase] += 1
            return
        if is_malformed_event(event):
            self.malformed_records += 1
            return
        key = dedupe_key or event.event_id
        if key in self._events:
            self.duplicate_collisions += 1
        self._events[key] = event

    def events(self) -> list[CalendarEvent]:
        return list(self._events.values())

    def metadata(self) -> dict[str, object]:
        phase_counts = Counter(event.competition_phase for event in self._events.values())
        return {
            "applied_options": self.options.to_dict(),
            "raw_record_count": self.raw_record_count,
            "kept_event_count": len(self._events),
            "dropped_duplicate_count": self.duplicate_collisions,
            "dropped_malformed_count": self.malformed_records,
            "dropped_by_phase": dict(self.dropped_by_phase),
            "kept_by_competition_phase": dict(phase_counts),
        }
