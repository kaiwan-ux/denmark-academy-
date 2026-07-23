import "./globals.css";
import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { AuthProvider } from "@/components/auth-provider";
import { LanguageProvider } from "@/components/language-provider";

export const metadata: Metadata = {
  title: "Denmark Academy",
  description: "Learning and official exam preparation for Danish PR and Citizenship exams",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="da" suppressHydrationWarning><body><LanguageProvider><AuthProvider><AppShell>{children}</AppShell></AuthProvider></LanguageProvider></body></html>;
}


