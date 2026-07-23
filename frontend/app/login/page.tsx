import { Suspense } from "react";
import { AuthForm } from "@/components/auth-form";
export default function LoginPage() { return <div className="auth-page"><Suspense fallback={null}><AuthForm mode="login" /></Suspense></div>; }

