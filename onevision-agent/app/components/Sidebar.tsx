"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const AGENT = process.env.NEXT_PUBLIC_AGENT_NAME || "VERA";

const LINKS = [
  { href: "/", icon: "◈", label: "Dashboard", badge: null },
  { href: "/chat", icon: "✦", label: "Ask VERA", badge: null },
  { href: "/clients", icon: "◐", label: "Clients", badge: null },
  { href: "/inbox", icon: "✉", label: "Inbox", badge: "inbox" },
  { href: "/revenue", icon: "$", label: "Revenue", badge: null },
  { href: "/tasks", icon: "✓", label: "Tasks", badge: "tasks" },
  { href: "/memory", icon: "◉", label: "Memory", badge: null },
  { href: "/alerts", icon: "!", label: "Alerts", badge: "alerts" },
  { href: "/settings", icon: "⚙", label: "Settings", badge: null },
] as const;

export default function Sidebar({
  counts,
}: {
  counts: { alerts: number; inbox: number; tasks: number };
}) {
  const path = usePathname();

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="agent">{AGENT}</div>
        <div className="rule" />
        <div className="org">One Vision</div>
      </div>

      <nav className="nav">
        {LINKS.map((l) => {
          const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
          const n = l.badge ? counts[l.badge as keyof typeof counts] : 0;
          return (
            <Link key={l.href} href={l.href} className={active ? "active" : ""}>
              <span className="ico">{l.icon}</span>
              <span>{l.label}</span>
              {n > 0 && <span className="badge">{n > 99 ? "99+" : n}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-foot">
        Chief of Staff
        <br />
        Isaiah Wright
      </div>
    </aside>
  );
}
