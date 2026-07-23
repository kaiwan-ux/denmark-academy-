"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { saveStudyActivity } from "@/lib/progress-client";

export type Account = {
  id: string;
  email: string;
  display_name: string;
  first_name?: string | null;
  last_name?: string | null;
  avatar_url?: string | null;
  preferred_track?: "pr" | "citizenship" | null;
  timezone: string;
  role: string;
  created_at: string;
  last_login_at?: string | null;
};

type AuthContextValue = {
  user: Account | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/account/auth/me", { cache: "no-store" });
      const data = await response.json();
      setUser(response.ok ? data.user : null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const logout = useCallback(async () => {
    try { await fetch("/api/account/auth/logout", { method: "POST" }); } finally {
      setUser(null);
      window.location.assign("/login");
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    let lastTick = Date.now();
    const flush = () => {
      const now = Date.now();
      const elapsed = Math.floor((now - lastTick) / 1000);
      if (elapsed > 0) {
        lastTick = now;
        void saveStudyActivity(elapsed, window.location.pathname + window.location.search);
      }
    };
    const interval = window.setInterval(flush, 30000);
    const handlePageHide = () => flush();
    window.addEventListener("pagehide", handlePageHide);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("pagehide", handlePageHide);
      flush();
    };
  }, [user]);
  const value = useMemo(() => ({ user, loading, refresh, logout }), [user, loading, refresh, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}


