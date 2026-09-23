// Incremental Server-Sent Events parser (GEN-007), shared by the /api/chat/stream route (reading
// the backend) and the chat page (reading the route). Chunks can split an event, a line, or a
// multi-byte character anywhere; `push` accepts raw bytes or text and emits whole events only.

export type SseEvent = { event: string; data: string };

export function formatSseEvent(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export class SseParser {
  private buffer = "";
  private decoder = new TextDecoder();
  private event = "";
  private data: string[] = [];
  private onEvent: (event: SseEvent) => void;

  constructor(onEvent: (event: SseEvent) => void) {
    this.onEvent = onEvent;
  }

  push(chunk: Uint8Array | string) {
    this.buffer += typeof chunk === "string" ? chunk : this.decoder.decode(chunk, { stream: true });
    let newline = this.buffer.search(/\r\n|\r|\n/);
    while (newline >= 0) {
      const line = this.buffer.slice(0, newline);
      const width = this.buffer.startsWith("\r\n", newline) ? 2 : 1;
      // A lone "\r" at the very end may be the first half of "\r\n": wait for the next chunk.
      if (width === 1 && this.buffer[newline] === "\r" && newline === this.buffer.length - 1) break;
      this.buffer = this.buffer.slice(newline + width);
      this.line(line);
      newline = this.buffer.search(/\r\n|\r|\n/);
    }
  }

  /** The stream ended: a final event without its blank line still counts. */
  end() {
    const rest = this.buffer + this.decoder.decode();
    this.buffer = "";
    if (rest) this.line(rest.replace(/\r$/, ""));
    this.dispatch();
  }

  private line(line: string) {
    if (line === "") {
      this.dispatch();
      return;
    }
    if (line.startsWith(":")) return; // comment / keep-alive
    const colon = line.indexOf(":");
    const field = colon < 0 ? line : line.slice(0, colon);
    let value = colon < 0 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") this.event = value;
    else if (field === "data") this.data.push(value);
  }

  private dispatch() {
    if (this.data.length) {
      this.onEvent({ event: this.event || "message", data: this.data.join("\n") });
    }
    this.event = "";
    this.data = [];
  }
}
