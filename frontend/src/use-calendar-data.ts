import { useEffect, useState, useSyncExternalStore } from "react";
import { CalendarDataStore } from "./data";

export function useCalendarData(
  anchors: string[],
  signature: string,
  timezone: string,
  retry: number,
) {
  const [store] = useState(() => new CalendarDataStore());
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot);
  const anchorsKey = JSON.stringify(anchors);
  useEffect(() => {
    store.update(JSON.parse(anchorsKey), signature, timezone, retry);
  }, [store, anchorsKey, signature, timezone, retry]);
  useEffect(() => () => store.cancel(), [store]);

  // Effects run after render: never expose the previous filter's events during
  // that render, and never retain data for months outside the requested window.
  const matching = store.matches(signature, timezone);
  const wanted = new Set(anchors);
  const years = new Set(anchors.map((anchor) => Number(anchor.slice(0, 4))));
  return {
    months: matching
      ? Object.fromEntries(
          Object.entries(state.months).filter(([anchor]) => wanted.has(anchor)),
        )
      : {},
    errors: Object.fromEntries(
      Object.entries(state.errors).filter(([year]) => years.has(Number(year))),
    ),
    loadingYears: matching
      ? state.loadingYears.filter((year) => years.has(year))
      : [...years],
    manifests: Object.fromEntries(
      Object.entries(state.manifests).filter(([year]) => years.has(Number(year))),
    ),
    facets: state.facets,
  };
}
