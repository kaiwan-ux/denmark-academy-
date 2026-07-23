"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, LogIn, LogOut, Menu, UserRound, X } from "lucide-react";
import { LibraryMotion } from "@/components/library-motion";
import { useAuth } from "@/components/auth-provider";
import { useLanguage } from "@/components/language-provider";

const nav = [
  ["/dashboard", "Home"],
  ["/reader/demo", "Reading"],
  ["/audio", "Audio"],
  ["/practice", "Past papers"],
  ["/revision", "Chapter practice"],
  ["/current-affairs", "Current affairs"],
  ["/exam-simulator", "Mock exam"]
];

export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { user, loading, logout } = useAuth();
  const { language, setLanguage } = useLanguage();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => { setMenuOpen(false); }, [path]);

  return (
    <div className={`site-shell ${menuOpen ? "mobile-menu-open" : ""}`}>
      <LibraryMotion />
      <div className="red-grid" />
      <header>
        <Link href="/dashboard" className="brand">
          <b>D</b><span><small>DENMARK</small>ACADEMY</span>
        </Link>
        <button type="button" className="menu-toggle" aria-label={menuOpen ? "Close navigation" : "Open navigation"} aria-expanded={menuOpen} onClick={() => setMenuOpen((value) => !value)}>
          {menuOpen ? <X size={21} aria-hidden /> : <Menu size={21} aria-hidden />}
        </button>
        <nav className="primary-nav" aria-label="Primary navigation">
          {nav.map(([href, label]) => <Link key={href} href={href} className={path === href || (href !== "/dashboard" && path.startsWith(href)) ? "active" : ""}>{label}</Link>)}
        </nav>
        <div className="account-nav">
          <div className="language-switcher" role="group" aria-label={language === "da" ? "VÃ¦lg sprog" : "Choose language"} data-preserve-language>
            <button type="button" className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")} aria-pressed={language === "en"}>EN</button>
            <span aria-hidden>/</span>
            <button type="button" className={language === "da" ? "active" : ""} onClick={() => setLanguage("da")} aria-pressed={language === "da"}>DA</button>
          </div>
          {!loading && user ? (
            <>
              <Link href="/progress" className={path === "/progress" ? "active" : ""} aria-label="My progress"><BarChart3 size={17}/><span>Progress</span></Link>
              <Link href="/profile" className={path === "/profile" ? "active" : ""} aria-label="Profile"><UserRound size={17}/><span>{user.display_name.split(" ")[0]}</span></Link>
              <button type="button" onClick={() => void logout()} aria-label="Log out"><LogOut size={17}/></button>
            </>
          ) : !loading ? <Link href={`/login?returnTo=${encodeURIComponent(path)}`}><LogIn size={17}/><span>Sign in</span></Link> : null}
        </div>
      </header>
      <main>{children}</main>
      <footer>
        <section><h2>DENMARK ACADEMY</h2><p>Focused preparation for Danish Permanent Residence and Citizenship exams.</p></section>
        <section><b>STUDY</b><Link href="/reader/demo">Reading â†’</Link><Link href="/practice">Past papers â†’</Link><Link href="/exam-simulator">Mock exam â†’</Link></section>
        <section><b>ACADEMY</b><Link href="/current-affairs">Current affairs â†’</Link><Link href="/revision">Chapter practice â†’</Link>{user ? <Link href="/progress">My progress â†’</Link> : <Link href="/login">Sign in â†’</Link>}</section>
      </footer>
    </div>
  );
}


