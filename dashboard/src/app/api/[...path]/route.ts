import { NextRequest, NextResponse } from "next/server";

const BASE = process.env.QH_API_BASE_URL?.replace(/\/$/, "");
const KEY = process.env.QH_API_KEY ?? "";
const ALLOWED = new Set(["state", "sweep", "simulate", "chat"]);

async function proxy(req: NextRequest, segments: string[]) {
  if (!BASE) return NextResponse.json({ ok: false, error: "QH_API_BASE_URL is not configured" }, { status: 500 });
  const [head] = segments;
  if (!(ALLOWED.has(head) || (head === "decisions" && segments.length === 2))) {
    return NextResponse.json({ ok: false, error: "unknown route" }, { status: 404 });
  }
  const body = req.method === "POST" ? await req.text() : undefined;
  const upstream = await fetch(`${BASE}/${segments.join("/")}`, {
    method: req.method,
    headers: { "content-type": "application/json", "x-api-key": KEY },
    body,
    cache: "no-store",
  });
  const text = await upstream.text();
  return new NextResponse(text, { status: upstream.status, headers: { "content-type": "application/json" } });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(req, (await ctx.params).path);
}
export const maxDuration = 300;
