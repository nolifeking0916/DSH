// CloudBase HTTP 函数的启动器：把平台的 HTTP 请求转成事件形状，交给 index.js 的 main，再写回响应。
// 端口：CloudBase 的 HTTP 函数固定 9000（也尊重 TCBRUNTIME_PORT / PORT）。
const http = require("node:http");
const { main } = require("./index.js");

const PORT = Number(process.env.TCBRUNTIME_PORT || process.env.PORT || 9000);

function toEvent(req) {
  const url = new URL(req.url, "http://localhost");
  const query = {};
  for (const [k, v] of url.searchParams) query[k] = v;
  const headers = {};
  for (const [k, v] of Object.entries(req.headers)) headers[k.toLowerCase()] = v;
  let body = "";
  req.on("data", (c) => { body += c; });
  return new Promise((resolve) => {
    req.on("end", () => resolve({
      httpMethod: req.method,
      path: url.pathname,
      headers,
      queryStringParameters: query,
      body,
      isBase64Encoded: false
    }));
  });
}

const server = http.createServer(async (req, res) => {
  try {
    const event = await toEvent(req);
    const out = await main(event) || { statusCode: 200, headers: {}, body: "{}" };
    const headers = out.headers || {};
    let body = out.body === undefined ? "" : out.body;
    if (headers["Content-Encoding"] === "base64" && event.isBase64Encoded) {
      body = Buffer.from(body, "base64");
    }
    res.writeHead(out.statusCode || 200, headers);
    res.end(body);
  } catch (e) {
    res.writeHead(500, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ ok: false, error: String(e && e.message || e) }));
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log("assessment function listening on " + PORT);
});
