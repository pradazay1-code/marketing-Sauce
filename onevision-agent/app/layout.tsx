import type { Metadata, Viewport } from "next";
import "./globals.css";
import { isAuthed } from "@/lib/auth";
import Sidebar from "./components/Sidebar";
import { sql } from "@/lib/db";

export const metadata: Metadata = {
  title: "VERA — One Vision Marketing",
  description: "Business agent for One Vision Marketing Agency",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

async function badges() {
  try {
    const [row] = await sql<{ alerts: number; inbox: number; tasks: number }>(
      `SELECT
         (SELECT count(*) FROM alerts WHERE acknowledged = false)::int AS alerts,
         (SELECT count(*) FROM emails WHERE needs_reply = true)::int   AS inbox,
         (SELECT count(*) FROM tasks WHERE status IN ('open','doing')
            AND priority IN ('urgent','high'))::int                    AS tasks`,
    );
    return row;
  } catch {
    // Schema not applied yet — render without badges rather than crashing.
    return { alerts: 0, inbox: 0, tasks: 0 };
  }
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const authed = await isAuthed();
  const counts = authed ? await badges() : { alerts: 0, inbox: 0, tasks: 0 };

  return (
    <html lang="en">
      <body>
        {authed ? (
          <div className="shell">
            <Sidebar counts={counts} />
            <div className="main">{children}</div>
          </div>
        ) : (
          children
        )}
      </body>
    </html>
  );
}
