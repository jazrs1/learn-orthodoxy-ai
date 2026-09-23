import "server-only";

// Where a request's time goes inside the site's routes (RET-018). Each route marks its steps and
// writes one JSON line (`event: "route_timing"`, in the Vercel logs), and the steps done before the
// response starts go out in a Server-Timing header, which the browser's resource timing exposes.
// The backend's X-Request-ID ties a line to the backend's own request log.

export class RouteTiming {
  private started = performance.now();
  private startEpochMs = Date.now();
  private durations: Record<string, number> = {};
  private fields: Record<string, unknown> = {};
  private route: string;

  constructor(route: string) {
    this.route = route;
  }

  /** Time since the route started, in ms. */
  now() {
    return Math.round(performance.now() - this.started);
  }

  /** Records when this step was reached (ms since the route started). */
  mark(name: string) {
    this.durations[name] = this.now();
  }

  /** Runs `work` and records how long it took. */
  async time<T>(name: string, work: () => Promise<T>): Promise<T> {
    const start = performance.now();
    try {
      return await work();
    } finally {
      this.durations[name] = Math.round(performance.now() - start);
    }
  }

  set(fields: Record<string, unknown>) {
    Object.assign(this.fields, fields);
  }

  /** `name;dur=ms` for each step so far, as a Server-Timing header value. */
  serverTiming() {
    return Object.entries(this.durations)
      .map(([name, ms]) => `${name};dur=${ms}`)
      .join(", ");
  }

  /** One JSON line on stdout (a structured log line, not debug output: UI-010's no-console rule). */
  log() {
    const line = {
      event: "route_timing",
      route: this.route,
      start_epoch_ms: this.startEpochMs,
      ...this.fields,
      ms: this.durations,
      total_ms: this.now(),
    };
    process.stdout.write(`${JSON.stringify(line)}
`);
  }
}
