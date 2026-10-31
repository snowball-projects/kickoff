import { useEffect, useRef, useState } from "react";
import { LEADERBOARD_URL, readLeaderboard, type GolfLeaderboardData } from "./golf";

export default function GolfLeaderboard({ id, date, today, timezone, active, onStatus, caption }: {
  id: string; date: string; today: string; timezone: string; active: boolean;
  onStatus?: (status: string | null) => void; caption?: string;
}) {
  const key = `${id}:${date}:${today}:${timezone}`;
  const [result, setResult] = useState<{ key: string; board: GolfLeaderboardData | null } | null>(null);
  const board = result?.key === key ? result.board : null;
  const root = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [pageVisible, setPageVisible] = useState(document.visibilityState === "visible");
  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting && entry.intersectionRatio > 0));
    observer.observe(root.current!);
    const visibility = () => setPageVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", visibility);
    return () => { observer.disconnect(); document.removeEventListener("visibilitychange", visibility); };
  }, []);
  useEffect(() => {
    if (!active || !visible || !pageVisible || date > today) return;
    const controller = new AbortController();
    let stopped = false;
    let inProgress = board?.inProgress ?? false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function refresh() {
      if (stopped || document.visibilityState !== "visible") return;
      try {
        // No custom headers: ESPN permits simple cross-origin GETs, not preflight.
        const response = await fetch(`${LEADERBOARD_URL}?event=${id}`, { signal: controller.signal });
        if (!response.ok) throw new Error("Leaderboard unavailable");
        const next = readLeaderboard(await response.json(), id, timezone, date < today);
        if (stopped) return;
        inProgress = next?.inProgress ?? false;
        setResult({ key, board: next });
        onStatus?.(next?.status ?? null);
      } catch {
        if (!stopped) { setResult({ key, board: null }); onStatus?.(null); }
      }
      if (!stopped && date === today && inProgress) timer = setTimeout(refresh, 60_000);
    }
    void refresh();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [id, date, today, timezone, active, visible, pageVisible, key, onStatus]);
  return <div className="golf-board" ref={root}>{board && <table className="golf-leaderboard">
    <caption>{caption || `${board.final ? "Final tournament top 5" : "Top 5"} · ESPN`}</caption>
    <thead><tr><th scope="col">Pos</th><th scope="col">Player</th><th scope="col">Total</th>
      <th scope="col">{board.final ? board.round ? `Round ${board.round}` : "Final round" : "Today"}</th><th scope="col">Thru</th></tr></thead>
    <tbody>{board.players.map((player) => <tr key={player.id}>
      <td>{player.position}</td><td>{player.name}</td><td>{player.total}</td><td>{player.today}</td><td>{player.thru}</td>
    </tr>)}</tbody>
  </table>}</div>;
}
