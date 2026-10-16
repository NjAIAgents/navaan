import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { OWNER } from "../components/Shell.test";

const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
const STATE = { state: "authed", user: "navjyot", idle_min: 43200, recovery_left: 7, passkey_ok: true, passkeys: [{ id: "pk1", name: "MacBook passkey", added: 1760000000 }] };
function route(routes: Record<string, (init?: RequestInit) => unknown>) {
  const f = vi.fn((u: string, init?: RequestInit) => {
    if (u.startsWith("/api/me")) return Promise.resolve(json(OWNER));
    const k = Object.keys(routes).sort((a, b) => b.length - a.length).find((r) => u === r || u.startsWith(r)); const v = k ? routes[k](init) : [];
    return Promise.resolve(v instanceof Response ? v : json(v));
  });
  vi.stubGlobal("fetch", f); return f;
}
const posts = (f: ReturnType<typeof route>, path: string) => f.mock.calls.filter(([u]) => u === path).map(([, i]) => JSON.parse(String(i?.body)));
const at = () => render(<MemoryRouter initialEntries={["/account/security"]}><App /></MemoryRouter>);
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Security (NAV-25)", () => {
  it("changes the password only with a long enough new one, and says other sessions end", async () => {
    const f = route({ "/auth/password": () => ({ ok: true }), "/auth/state": () => STATE });
    at(); const change = await screen.findByRole("button", { name: "Change password" }); expect(change).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "old-pass-word" } }); fireEvent.change(screen.getByLabelText(/^New password/), { target: { value: "short" } }); expect(change).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/^New password/), { target: { value: "a-much-longer-password" } }); fireEvent.click(change);
    await waitFor(() => expect(posts(f, "/auth/password")).toEqual([{ password: "old-pass-word", new: "a-much-longer-password" }])); expect(await screen.findByText(/other sessions are signed out/)).toBeInTheDocument();
  });
  it("shows a refused password step", async () => {
    route({ "/auth/recovery": () => json({ error: "wrong password" }, 403), "/auth/state": () => STATE });
    at(); fireEvent.change(await screen.findByLabelText("Current password"), { target: { value: "nope" } }); fireEvent.click(screen.getByRole("button", { name: /New recovery codes/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("wrong password");
  });
  it("shows new recovery codes once", async () => {
    route({ "/auth/recovery": () => ({ recovery: ["aaaa-bbbb", "cccc-dddd"] }), "/auth/state": () => STATE });
    at(); fireEvent.change(await screen.findByLabelText("Current password"), { target: { value: "old-pass-word" } }); fireEvent.click(screen.getByRole("button", { name: /New recovery codes/ }));
    expect(await screen.findByLabelText("New recovery codes")).toHaveTextContent("aaaa-bbbb");
  });
  it("removes a passkey after a confirmation", async () => {
    const f = route({ "/auth/passkey/remove": () => ({ ok: true }), "/auth/state": () => STATE });
    at(); fireEvent.click(await screen.findByRole("button", { name: "Remove MacBook passkey" })); expect(posts(f, "/auth/passkey/remove")).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Yes, remove" })); await waitFor(() => expect(posts(f, "/auth/passkey/remove")).toEqual([{ id: "pk1" }]));
  });
  it("has no serious accessibility violations", async () => {
    route({ "/auth/state": () => STATE });
    const { container } = at(); await screen.findByRole("heading", { name: "Passkeys" });
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } }); expect(r.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
  });
});
