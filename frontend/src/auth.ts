import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

// Email whitelist - loaded from env variable
// Format: comma-separated emails, e.g., "admin@example.com,user@example.com"
const ALLOWED_EMAILS = process.env.ALLOWED_EMAILS?.split(',').map(e => e.trim()).filter(Boolean) || [];

export const { auth, handlers, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID,
      clientSecret: process.env.AUTH_GOOGLE_SECRET,
    }),
  ],
  callbacks: {
    async signIn({ user, profile }) {
      // Require verified email
      const googleProfile = profile as { email_verified?: boolean } | undefined;
      if (!googleProfile?.email_verified) {
        console.log('[Auth] Rejected: Email not verified');
        return false;
      }

      // If whitelist is configured, check if user email is allowed
      if (ALLOWED_EMAILS.length > 0 && user.email) {
        const isAllowed = ALLOWED_EMAILS.includes(user.email.toLowerCase());
        if (!isAllowed) {
          console.log('[Auth] Rejected: Email not in whitelist:', user.email);
          return '/auth/denied';
        }
        console.log('[Auth] Allowed: Email in whitelist:', user.email);
      }

      console.log('[Auth] Sign in successful:', user.email);
      return true;
    },
    async session({ session, token }) {
      // Add user ID to session
      if (session.user && token.sub) {
        session.user.id = token.sub;
      }
      return session;
    },
    async jwt({ token, user }) {
      // Persist user ID to token
      if (user?.id) {
        token.sub = user.id;
      }
      return token;
    },
  },
  pages: {
    signIn: '/login',
    error: '/auth/error',
  },
  session: {
    strategy: 'jwt',
  },
  trustHost: true,
});
