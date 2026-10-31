import assets from "./team-assets.json";

const byName = new Map(Object.values(assets).map((asset) => [asset.name, asset]));
export default function NflLogo({ name, league }: { name: string; league: string }) {
  const asset = league === "NFL" ? byName.get(name) : undefined;
  return asset ? <img className="nfl-logo" src={`${import.meta.env.BASE_URL}${asset.url}`} width="28" height="28" alt="" loading="lazy" /> : null;
}
