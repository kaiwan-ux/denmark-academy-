import { NextRequest, NextResponse } from "next/server";

const protectedPrefixes = [
  "/reader",
  "/knowledge",
  "/revision",
  "/practice",
  "/current-affairs",
  "/adaptive",
  "/exam-simulator",
  "/ai",
  "/mentor",
  "/graph",
  "/search",
  "/progress",
  "/profile",
  "/notes",
];

export function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const requiresAuth = protectedPrefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
  if (!requiresAuth || request.cookies.has("da_session")) return NextResponse.next();

  const login = new URL("/login", request.url);
  login.searchParams.set("returnTo", `${pathname}${request.nextUrl.search}`);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};


