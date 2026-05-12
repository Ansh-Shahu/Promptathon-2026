import { Link } from "@tanstack/react-router";
import logo from "@/assets/carrier-logo.png";

const nav = ["Vision", "Components", "Solutions", "Performance"];

export function Header() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2.5">
          <img src={logo} alt="Carrier" className="h-7 w-auto" />
          <span className="text-[15px] font-bold tracking-tight text-foreground">
            Carrier <span className="text-primary">Ai</span>
          </span>
        </Link>
        <nav className="hidden items-center gap-8 md:flex">
          {nav.map((n) => (
            <a
              key={n}
              href={`#${n.toLowerCase()}`}
              className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground transition-colors hover:text-foreground"
            >
              {n}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <a
            href="#login"
            className="hidden h-9 items-center justify-center rounded-full border border-border bg-card px-4 text-xs font-semibold uppercase tracking-wider text-foreground transition-colors hover:border-primary/50 sm:inline-flex"
          >
            Log in
          </a>
          <a
            href="#dashboard"
            className="inline-flex h-9 items-center justify-center gap-2 rounded-full bg-gradient-cta px-4 text-xs font-semibold uppercase tracking-wider text-primary-foreground shadow-card transition-all hover:-translate-y-0.5 hover:shadow-elevated"
          >
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M3 12h3l2-7 4 14 2-7h7" />
            </svg>
            Dashboard
          </a>
        </div>
      </div>
    </header>
  );
}
