import { useEffect, useState } from "react";
import { LEADERBOARD_URL, readLeaderboard, type GolfLeaderboardData } from "./golf";

export default function GolfLeaderboard({ id, date, today, timezone, active }: {
  id: string; date: string; today: string; timezone: string; active: boolean;
}) {
  const [board, setBoard] = useState<GolfLeaderboardData | null>(null);
  useEffect(() => {
    if (!active || date > today) return;
    const controller = new AbortController();
    let stopped = false;
    let inProgress = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function refresh() {
      try {
        // No custom headers: ESPN permits simple cross-origin GETs, not preflight.
        const response = await fetch(`${LEADERBOARD_URL}?event=${id}`, { signal: controller.signal });
        if (!response.ok) throw new Error("Leaderboard unavailable");
        const next = readLeaderboard(await response.json(), id, timezone, date < today);
        if (stopped) return;
        inProgress = next?.inProgress ?? false;
        setBoard(next);
      } catch {
        if (!stopped) setBoard(null);
      }
      if (!stopped && date === today && inProgress) timer = setTimeout(refresh, 60_000);
    }
    void refresh();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [id, date, today, timezone, active]);
  if (!board) return null;
  return <table className="golf-leaderboard">
    <caption>{board.final ? "Final tournament top 5" : "Top 5"} · ESPN</caption>
    <thead><tr><th scope="col">Pos</th><th scope="col">Player</th><th scope="col">Total</th>
      <th scope="col">{board.final ? board.round ? `Round ${board.round}` : "Final round" : "Today"}</th><th scope="col">Thru</th></tr></thead>
    <tbody>{board.players.map((player) => <tr key={player.id}>
      <td>{player.position}</td><td>{player.name}</td><td>{player.total}</td><td>{player.today}</td><td>{player.thru}</td>
    </tr>)}</tbody>
  </table>;
}
