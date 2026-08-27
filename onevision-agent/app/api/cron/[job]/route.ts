import { NextResponse } from "next/server";
import { isCronAuthorized, isAuthed } from "@/lib/auth";
import { runJob, type JobName } from "@/lib/jobs";

export const runtime = "nodejs";
export const maxDuration = 300;

const VALID: JobName[] = ["sync", "morning-brief", "client-review", "watchdog"];

/** Vercel Cron hits this on schedule; the Settings page can also fire it manually. */
export async function GET(
  req: Request,
  { params }: { params: Promise<{ job: string }> },
) {
  const { job } = await params;

  if (!VALID.includes(job as JobName)) {
    return NextResponse.json(
      { error: `Unknown job "${job}". Valid: ${VALID.join(", ")}` },
      { status: 404 },
    );
  }

  // Either Vercel Cron (bearer secret) or a signed-in human pressing "Run now".
  const authorized = isCronAuthorized(req) || (await isAuthed());
  if (!authorized) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const started = Date.now();
  const result = await runJob(job as JobName);

  return NextResponse.json(
    { job, ...result, ms: Date.now() - started },
    { status: result.ok ? 200 : 500 },
  );
}

export const POST = GET;
