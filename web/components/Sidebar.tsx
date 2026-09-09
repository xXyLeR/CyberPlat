"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/labs", label: "Labs" },
  { href: "/learning-paths", label: "Learning Paths" },
  { href: "/ctf", label: "CTF" },
  { href: "/assessments", label: "Assessments" },
  { href: "/reports", label: "Reports" },
  { href: "/teams", label: "Teams" },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-panel">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="h-2 w-2 rounded-full bg-trace shadow-[0_0_8px_2px_rgba(79,216,232,0.6)]" />
        <span className="font-mono text-sm tracking-tight text-ink">vantage_range</span>
      </div>

      <nav className="flex-1 px-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname?.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`mb-0.5 flex items-center rounded px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-panel-raised text-ink border-l-2 border-trace pl-[10px]"
                  : "text-ink-muted hover:bg-panel-raised hover:text-ink"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border p-3">
        <button
          onClick={() => {
            clearToken();
            router.push("/login");
          }}
          className="w-full rounded px-3 py-2 text-left text-sm text-ink-muted hover:bg-panel-raised hover:text-danger"
        >
          Sair
        </button>
      </div>
    </aside>
  );
}
