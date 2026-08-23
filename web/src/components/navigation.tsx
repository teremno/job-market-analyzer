"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["/", "Overview", "01"],
  ["/jobs", "Jobs", "02"],
  ["/roles", "Roles", "03"],
  ["/skills", "Skills", "04"],
  ["/gap", "Skill gap", "05"],
  ["/sources", "Sources", "06"],
] as const;

export function Navigation() {
  const pathname = usePathname();
  return (
    <nav className="nav" aria-label="Primary navigation">
      {links.map(([href, label, index]) => {
        const active = href === "/" ? pathname === href : pathname.startsWith(href);
        return (
          <Link key={href} href={href} className={active ? "nav-link active" : "nav-link"}>
            <span aria-hidden="true">{index}</span>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
