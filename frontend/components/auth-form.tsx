"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail, UserRound } from "lucide-react";
import { useAuth } from "@/components/auth-provider";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const search = useSearchParams();
  const { refresh } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const isSignup = mode === "signup";

  function safeReturnTo() {
    const value = search.get("returnTo") || "/progress";
    return value.startsWith("/") && !value.startsWith("//") ? value : "/progress";
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const payload = {
      email: String(form.get("email") || ""),
      password: String(form.get("password") || ""),
      remember_me: form.get("remember_me") === "on",
      ...(isSignup ? { display_name: String(form.get("display_name") || "") } : {}),
    };
    try {
      const response = await fetch(`/api/account/auth/${mode}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = data.detail;
        throw new Error(Array.isArray(detail) ? detail[0]?.msg || "Check your details and try again." : detail || "Unable to continue.");
      }
      await refresh();
      router.replace(safeReturnTo());
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to continue.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="auth-card" aria-labelledby="auth-title">
      <div className="auth-card-intro">
        <div className="auth-kicker"><LockKeyhole size={15} aria-hidden /> Secure learning account</div>
        <h1 id="auth-title">{isSignup ? "Create your study record." : "Welcome back."}</h1>
        <p>{isSignup ? "Save every answer, note, bookmark and reading position across all your devices." : "Continue from the exact lesson or question where you stopped."}</p>
        <div className="auth-benefits">
          <span>Permanent progress</span><span>Private study history</span><span>Continue learning</span>
        </div>
      </div>
      <form onSubmit={submit} className="auth-form">
        <div>
          <span className="auth-step">{isSignup ? "01 / CREATE ACCOUNT" : "01 / SIGN IN"}</span>
          <h2>{isSignup ? "Your details" : "Account access"}</h2>
        </div>
        {isSignup ? (
          <label>
            <span>Full name</span>
            <div className="auth-input"><UserRound size={18} aria-hidden /><input name="display_name" autoComplete="name" required minLength={2} placeholder="Your name" /></div>
          </label>
        ) : null}
        <label>
          <span>Email address</span>
          <div className="auth-input"><Mail size={18} aria-hidden /><input name="email" type="email" autoComplete="email" required placeholder="you@example.com" /></div>
        </label>
        <label>
          <span>Password</span>
          <div className="auth-input"><LockKeyhole size={18} aria-hidden /><input name="password" type={showPassword ? "text" : "password"} autoComplete={isSignup ? "new-password" : "current-password"} required minLength={8} placeholder="At least 8 characters" /><button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>
        </label>
        <div className="auth-form-row">
          <label className="remember"><input name="remember_me" type="checkbox" /><span>Remember me for 30 days</span></label>
        </div>
        {error ? <div className="auth-error" role="alert">{error}</div> : null}
        <button className="auth-submit" type="submit" disabled={pending}>{pending ? "Please wait…" : isSignup ? "Create account" : "Sign in"}<ArrowRight size={18} aria-hidden /></button>
        <p className="auth-switch">{isSignup ? "Already have an account?" : "New to Denmark Academy?"} <Link href={`${isSignup ? "/login" : "/signup"}?returnTo=${encodeURIComponent(safeReturnTo())}`}>{isSignup ? "Sign in" : "Create account"}</Link></p>
      </form>
    </section>
  );
}

