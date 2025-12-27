import { auth } from "@/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const isLoggedIn = !!req.auth;
  const { pathname } = req.nextUrl;

  // Public routes that don't require auth
  const isAuthPage = pathname.startsWith('/login') || pathname.startsWith('/auth');
  const isApiAuth = pathname.startsWith('/api/auth');
  const isPublicApi = pathname.startsWith('/api/health');

  // Always allow auth endpoints and health check
  if (isApiAuth || isPublicApi) {
    return NextResponse.next();
  }

  // Redirect to login if not authenticated (except on auth pages)
  if (!isLoggedIn && !isAuthPage) {
    const loginUrl = new URL('/login', req.url);
    loginUrl.searchParams.set('callbackUrl', pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Redirect to home if already logged in and on login page
  if (isLoggedIn && isAuthPage) {
    return NextResponse.redirect(new URL('/', req.url));
  }

  return NextResponse.next();
});

export const config = {
  // Protect all routes except static files and specific public paths
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|icon-.*\\.png|manifest\\.json|sw\\.js|workbox-.*\\.js|api/files).*)',
  ],
};
