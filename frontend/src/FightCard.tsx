import { useEffect, useId, useState } from "react";
import { fightCardRequest, readFightCard, type FightCardData } from "./fights";
import type { EventCard } from "./types";

export default function FightCard({ event, timezone, active }: { event: EventCard; timezone: string; active: boolean }) {
  const request = fightCardRequest(event);
  const key = `${event.event_id}:${request?.url}`;
  const [result, setResult] = useState<{ key: string; card: FightCardData; checked: string } | null>(null);
  const [selected, setSelected] = useState(0);
  const id = useId();
  const card = result?.key === key ? result.card : null;
  const url = request?.url;
  useEffect(() => {
    setSelected(0);
    if (!active || !request) return;
    const controller = new AbortController();
    let stopped = false;
    async function load() {
      try {
        // A simple GET avoids a cross-origin preflight, like the golf leaderboard.
        const response = await fetch(url!, { signal: controller.signal });
        if (!response.ok) return;
        const next = readFightCard(await response.json(), request!);
        if (!stopped && next) setResult({ key, card: next, checked: new Date().toISOString().slice(0, 10) });
      } catch { /* The schedule and its source remain visible when ESPN is unavailable. */ }
    }
    void load();
    return () => { stopped = true; controller.abort(); };
  }, [key, url, active]);
  if (!card) return null;
  const time = (start: string) => new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit", timeZone: timezone }).format(Date.parse(start));
  const block = card.blocks[selected] || card.blocks[0];
  return <section className="fight-card" aria-label="Fight card">
    <div className="fight-tabs" role="tablist" aria-label="Card segments">
      {card.blocks.map((item, index) => <button key={item.start} role="tab" id={`${id}-tab-${index}`}
        aria-selected={selected === index} aria-controls={`${id}-panel`} tabIndex={selected === index ? 0 : -1}
        onClick={() => setSelected(index)} onKeyDown={(event) => {
          let next = index;
          if (event.key === "ArrowRight") next = (index + 1) % card.blocks.length;
          else if (event.key === "ArrowLeft") next = (index + card.blocks.length - 1) % card.blocks.length;
          else if (event.key === "Home") next = 0;
          else if (event.key === "End") next = card.blocks.length - 1;
          else return;
          event.preventDefault(); setSelected(next); document.getElementById(`${id}-tab-${next}`)?.focus();
        }}>{item.label || time(item.start)}</button>)}
    </div>
    <div role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-tab-${selected}`}>
      <p className="fight-start">{time(block.start)}</p>
      <ol className="fight-bouts">{block.bouts.map((bout) => <li key={bout.id}>
        <div className="fight-matchup">
          <div className="fight-fighter"><b>{bout.fighters[0].name}</b><span>{bout.fighters[0].record}{bout.fighters[0].winner && <strong>Winner</strong>}</span></div>
          <span className="fight-weight">{bout.weight}</span>
          <div className="fight-fighter"><b>{bout.fighters[1].name}</b><span>{bout.fighters[1].record}{bout.fighters[1].winner && <strong>Winner</strong>}</span></div>
        </div>
        {bout.result && <p className="fight-result">{bout.result}</p>}
      </li>)}</ol>
    </div>
    <a className="fight-source" href={card.sourceUrl} target="_blank" rel="noreferrer">Fight card · ESPN ↗</a>
    <span className="fight-checked">Checked {result!.checked}</span>
  </section>;
}
