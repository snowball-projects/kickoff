import TeamLogo from "./TeamLogo";
import { completedTeams, teamOutcome } from "./team-results";
import type { EventCard } from "./types";
import "./results.css";
import "./team-results.css";

export default function TeamResultDetails({ event }: { event: EventCard }) {
  const teams = completedTeams(event);
  if (!teams.length) return null;
  const aggregate = teams.some(team => team.aggregate_score != null);
  const shootout = teams.some(team => team.shootout_score != null);
  return <section className="event-result-details team-result-details" aria-label="Match result">
    <h4>Final</h4>
    <div className="event-result-table-wrap"><table aria-label="Final team scores" className="event-result-team">
      <thead><tr><th scope="col">Team</th><th scope="col">Score</th>{aggregate && <th scope="col">Aggregate</th>}{shootout && <th scope="col">Shootout</th>}</tr></thead>
      <tbody>{teams.map((team, index) => {
        const outcome = teamOutcome(team, teams[1 - index], event.sport);
        return <tr key={index} className={outcome.winner ? "event-result-match-winner" : undefined}>
          <th scope="row"><span className="team-result-name"><TeamLogo participant={team} />{team.name}</span>{outcome.winner && <small>Winner</small>}{outcome.advances && <small>Advances</small>}</th>
          <td>{team.final_score}</td>{aggregate && <td>{team.aggregate_score}</td>}{shootout && <td>{team.shootout_score}</td>}
        </tr>;
      })}</tbody>
    </table></div>
  </section>;
}
