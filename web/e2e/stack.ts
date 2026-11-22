import { spawn, type ChildProcess } from "node:child_process";
import net from "node:net";

/**
 * An isolated copy of the app (production build) wired to its own mock API, for tests that need a
 * backend that fails or is slow. Server-rendered pages call the API from the server, so
 * `page.route()` cannot simulate that; a real second backend can. Needs `npm run build` first.
 */
export interface Stack {
  baseURL: string;
  stop(): Promise<void>;
}

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.on("error", reject);
    s.listen(0, "127.0.0.1", () => {
      const { port } = s.address() as net.AddressInfo;
      s.close(() => resolve(port));
    });
  });
}

async function waitFor(url: string, timeoutMs: number) {
  const until = Date.now() + timeoutMs;
  for (;;) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // not up yet
    }
    if (Date.now() > until) throw new Error(`Timed out waiting for ${url}`);
    await new Promise((r) => setTimeout(r, 400));
  }
}

function kill(p: ChildProcess): Promise<void> {
  return new Promise((resolve) => {
    if (!p.pid || p.exitCode !== null) return resolve();
    if (process.platform === "win32") {
      spawn("taskkill", ["/PID", String(p.pid), "/T", "/F"], { stdio: "ignore" }).on("close", () =>
        resolve(),
      );
    } else {
      try {
        process.kill(-p.pid, "SIGTERM");
      } catch {
        // already gone
      }
      resolve();
    }
  });
}

export async function startStack(opts: { fail?: boolean; delayMs?: number } = {}): Promise<Stack> {
  const apiPort = await freePort();
  const webPort = await freePort();
  const win = process.platform === "win32";
  const procs: ChildProcess[] = [];
  const run = (cmd: string, args: string[], env: Record<string, string>) => {
    const p = spawn(cmd, args, {
      env: { ...process.env, ...env },
      stdio: "ignore",
      shell: win,
      detached: !win,
    });
    procs.push(p);
  };

  run("node", ["e2e/mock-api.mjs"], {
    MOCK_API_PORT: String(apiPort),
    MOCK_API_FAIL: opts.fail ? "1" : "0",
    MOCK_API_DELAY_MS: String(opts.delayMs ?? 0),
  });
  run("npx", ["next", "start", "-p", String(webPort)], {
    API_URL: `http://127.0.0.1:${apiPort}`,
    NEXT_TELEMETRY_DISABLED: "1",
  });

  try {
    await waitFor(`http://127.0.0.1:${apiPort}/health`, 30_000);
    await waitFor(`http://127.0.0.1:${webPort}/offline`, 90_000);
  } catch (e) {
    await Promise.all(procs.map(kill));
    throw e;
  }
  return {
    baseURL: `http://127.0.0.1:${webPort}`,
    stop: async () => void (await Promise.all(procs.map(kill))),
  };
}
