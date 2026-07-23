import { Suspense } from "react";
import { AuthForm } from "@/components/auth-form";
export default function SignupPage() { return <div className="auth-page"><Suspense fallback={null}><AuthForm mode="signup" /></Suspense></div>; }

