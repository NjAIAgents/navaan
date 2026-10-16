import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getJSON, type Alert } from "../lib/api";

type State = { scheduler?: string; worker?: string };

// What needs the owner now, on every studio screen: an expired sign in, the scheduler paused, the worker down. Each says where to fix it.
export function Alerts() {
  const [items, setItems] = useState<{ id: string; title: string; message: string }[]>([]);
  useEffect(() => {
    let live = true;
    Promise.all([getJSON<{ alerts: Alert[] }>("/api/alerts").catch(() => ({ alerts: [] as Alert[] })), getJSON<State>("/auth/state").catch(() => ({} as State))]).then(([a, s]) => {
      if (!live) return;
      const out = (a.alerts ?? []).map(({ id, title, message }) => ({ id, title, message }));
      if (s.scheduler === "paused") out.push({ id: "scheduler", title: "The schedule is paused", message: "Publishing waits until the secrets from Vault are available." });
      if (s.worker === "down") out.push({ id: "worker", title: "The worker is down", message: "Steps are queued but nothing will run them until the worker is back." });
      setItems(out);
    });
    return () => { live = false; };
  }, []);
  if (!items.length) return null;
  return (
    <section className="card" role="region" aria-label="Needs attention">
      <h2>Needs attention</h2>
      <ul>{items.map((i) => <li key={i.id}><b>{i.title}.</b> <span className="mu">{i.message}</span> <Link to="/studio/settings">Open Settings</Link></li>)}</ul>
    </section>
  );
}
