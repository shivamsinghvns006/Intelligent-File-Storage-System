import assert from "node:assert/strict";
import test from "node:test";

import { checkApiHealth } from "./health-client.mjs";

test("reports connected only for a successful IFSS health response", async () => {
  let requestedUrl;
  const status = await checkApiHealth("http://localhost:8000", async (url) => {
    requestedUrl = url.toString();
    return Response.json({ status: "ok" });
  });

  assert.equal(requestedUrl, "http://localhost:8000/health");
  assert.equal(status, "connected");
});

test("reports unavailable for unsuccessful or unexpected responses", async () => {
  const httpError = await checkApiHealth("http://localhost:8000", async () =>
    new Response(null, { status: 503 }),
  );
  const unexpectedBody = await checkApiHealth("http://localhost:8000", async () =>
    Response.json({ status: "starting" }),
  );

  assert.equal(httpError, "unavailable");
  assert.equal(unexpectedBody, "unavailable");
});

test("reports unavailable when the API cannot be reached", async () => {
  const status = await checkApiHealth("http://localhost:8000", async () => {
    throw new TypeError("network failure with details that must not reach the UI");
  });

  assert.equal(status, "unavailable");
});
