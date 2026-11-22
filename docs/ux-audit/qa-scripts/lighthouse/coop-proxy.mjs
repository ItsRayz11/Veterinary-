// TOOLING ONLY (never shipped): pass-through proxy to the local app that drops ONE response header,
// to test whether it is what makes Lighthouse lose navigationStart.
import http from "node:http";
const DROP = (process.env.DROP ?? "cross-origin-opener-policy").split(",");
http.createServer((req, res) => {
  const headers = { ...req.headers, host: "127.0.0.1:3100", "accept-encoding": "identity" };
  const up = http.request({ host: "127.0.0.1", port: 3100, path: req.url, method: req.method, headers }, (r) => {
    const out = { ...r.headers }; for (const h of DROP) delete out[h];
    res.writeHead(r.statusCode ?? 200, out); r.pipe(res);
  });
  up.on("error", () => { res.writeHead(502); res.end("proxy error"); });
  req.pipe(up);
}).listen(Number(process.env.PORT ?? 3300), "127.0.0.1", () => console.log("proxy up, dropping:", DROP.join()));
