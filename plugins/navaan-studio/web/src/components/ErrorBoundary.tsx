import { Component, type ReactNode } from "react";
import { postJSON } from "../lib/api";

// A screen that throws shows what happened and a way on, instead of a black page. The error is reported to the server log like any other browser error.
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error) {
    void postJSON("/api/client-log", { kind: "error", message: error.message, stack: error.stack ?? "", page: location.pathname, where: "render" }).catch(() => undefined);   // expected: the report is best effort
  }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="card stack" role="alert">
        <h2>This screen hit a problem</h2>
        <p className="mu">{this.state.error.message || "Something went wrong while showing it."} It has been reported. The rest of the app still works.</p>
        <div className="row"><button className="btn p" onClick={() => location.reload()}>Reload</button><a className="btn g" href="/app/">Go home</a></div>
      </div>
    );
  }
}
