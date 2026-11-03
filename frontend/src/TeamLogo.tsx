import { useEffect, useRef, useState } from "react";
import type { ApiParticipant } from "./types";

function LogoImage({ url, load, onError }: { url: string; load: boolean; onError?: () => void }) {
  const image = useRef<HTMLImageElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const element = image.current;
    if (!load || !element) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting && entry.intersectionRatio > 0)) {
        setVisible(true);
        observer.disconnect();
      }
    }, { rootMargin: "0px", threshold: .01 });
    observer.observe(element);
    return () => observer.disconnect();
  }, [load]);
  return <img ref={image} className="team-logo" src={load && visible ? url : undefined}
    width="28" height="28" alt="" loading="lazy" referrerPolicy="no-referrer"
    onError={(event) => { event.currentTarget.hidden = true; onError?.(); }} />;
}

export default function TeamLogo({ participant, load = true, onError }: {
  participant?: ApiParticipant | null; load?: boolean; onError?: () => void;
}) {
  const url = participant?.logo_url;
  return url ? <LogoImage key={`${load}:${url}`} url={url} load={load} onError={onError} /> : null;
}
