// Retrying a step that can fail for a moment, such as a database write while Neon wakes from
// suspend (~2 s after 5 minutes idle, RET-020). Used for saving a finished answer (RET-021).

export type RetryOptions = {
  /** Pauses before the second, third… attempt; one attempt more than there are delays. */
  delaysMs: number[];
  /** Errors that can't be cured by waiting (missing configuration) fail at once. */
  shouldRetry?: (error: unknown) => boolean;
  sleep?: (ms: number) => Promise<void>;
};

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export async function withRetry<T>(work: (attempt: number) => Promise<T>, options: RetryOptions): Promise<T> {
  const { delaysMs, shouldRetry = () => true, sleep = wait } = options;
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await work(attempt);
    } catch (error) {
      if (attempt >= delaysMs.length || !shouldRetry(error)) throw error;
      await sleep(delaysMs[attempt]);
    }
  }
}
