"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function RunJobs({ job }: { job: string }) {
  const [state, setState] = useState<"idle" | "running" | "ok" | "err">("idle");
  const router = useRouter();

  async function run() {
    setState("running");
    try {
      const res = await fetch(`/api/cron/${job}`, { method: "POST" });
      setState(res.ok ? "ok" : "err");
      router.refresh();
    } catch {
      setState("err");
    }
    setTimeout(() => setState("idle"), 4000);
  }

  const label =
    state === "running" ? "Running…" : state === "ok" ? "Done" : state === "err" ? "Failed" : "Run now";

  return (
    <button className="btn ghost sm" onClick={run} disabled={state === "running"}>
      {label}
    </button>
  );
}
