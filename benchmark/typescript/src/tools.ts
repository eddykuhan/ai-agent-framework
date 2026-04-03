/**
 * Tool implementations for the TypeScript MCP benchmark server.
 * Mirrors the Python implementations exactly for fair comparison.
 */

import Ajv from "ajv";

const ajv = new Ajv();

// ---------------------------------------------------------------------------
// Semaphore — used by batchProcess for bounded concurrency
// ---------------------------------------------------------------------------
class Semaphore {
  private running = 0;
  private readonly queue: Array<() => void> = [];

  constructor(private readonly limit: number) {}

  run<T>(fn: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      const attempt = () => {
        if (this.running < this.limit) {
          this.running++;
          fn()
            .then(resolve, reject)
            .finally(() => {
              this.running--;
              this.queue.shift()?.();
            });
        } else {
          this.queue.push(attempt);
        }
      };
      attempt();
    });
  }
}

// ---------------------------------------------------------------------------
// Tool implementations
// ---------------------------------------------------------------------------

function fibRecursive(n: number): number {
  if (n <= 1) return n;
  return fibRecursive(n - 1) + fibRecursive(n - 2);
}

export async function echo(text: string) {
  return { echo: text, length: text.length };
}

export async function fibonacci(n: number) {
  const start = performance.now();
  const result = fibRecursive(n);
  return { n, result, elapsed_ms: +((performance.now() - start)).toFixed(3) };
}

export async function fetchMock(delay_ms = 50, url = "https://example.com") {
  await new Promise<void>((r) => setTimeout(r, delay_ms));
  return { url, delay_ms, status: 200, body_length: 1024 };
}

export async function batchProcess(items: unknown[], concurrency = 10) {
  const start = performance.now();
  const sem = new Semaphore(concurrency);
  const results = await Promise.all(
    items.map((item) =>
      sem.run(async () => {
        await new Promise<void>((r) => setTimeout(r, 1));
        return { item, processed: true };
      })
    )
  );
  return {
    count: results.length,
    elapsed_ms: +((performance.now() - start)).toFixed(3),
    concurrency,
  };
}

export async function validateSchema(data: unknown, schema: object) {
  let validate: ReturnType<typeof ajv.compile>;
  try {
    validate = ajv.compile(schema);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return { valid: false, errors: [`Invalid schema: ${msg}`] };
  }
  const valid = validate(data) as boolean;
  return {
    valid,
    errors: valid ? [] : (validate.errors?.map((e) => e.message ?? String(e)) ?? []),
  };
}
