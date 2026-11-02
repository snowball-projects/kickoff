import type { ApiParticipant } from "./types";
import { espnLogoUrl } from "./team-logo";
import assets from "./team-assets.json";

const byName = new Map(Object.values(assets).map((asset) => [asset.name, asset]));
export function hasNflLogo(name: string) { return byName.has(name); }
export default function NflLogo({ name, league, participant }: { name: string; league: string; participant?: ApiParticipant }) {
  const asset = league === "NFL" ? byName.get(name) : undefined;
  const supplied = espnLogoUrl(participant?.logo_url);
  if (!asset && supplied) return <img key={supplied} className="nfl-logo" src={supplied} width="28" height="28" alt=""
    loading="lazy" referrerPolicy="no-referrer" onError={(event) => { event.currentTarget.hidden = true; }} />;
  return asset ? <img className="nfl-logo" src={`${import.meta.env.BASE_URL}${asset.url}`} width="28" height="28" alt="" loading="lazy" /> : null;
}
