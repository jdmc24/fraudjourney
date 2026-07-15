import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET() {
  const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8001";

  try {
    const response = await fetch(`${backendUrl}/api/evaluations`, {
      // Evaluation results are generated from deterministic local cases.
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    return NextResponse.json(await response.json());
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "unknown backend failure";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
