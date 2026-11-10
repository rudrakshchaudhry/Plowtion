import type { NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";

// AUTH_* names are the Auth.js v5 defaults; the older NEXTAUTH_SECRET /
// GOOGLE_CLIENT_* names are still accepted.
const googleId = process.env.AUTH_GOOGLE_ID || process.env.GOOGLE_CLIENT_ID;
const googleSecret = process.env.AUTH_GOOGLE_SECRET || process.env.GOOGLE_CLIENT_SECRET;
const secret = process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET;

// Google sign-in is enabled only when all three values are configured. Otherwise
// the app runs without authentication and the sign-in buttons are hidden.
export const authEnabled = Boolean(googleId && googleSecret && secret);

export default {
    trustHost: true,
    providers: authEnabled ? [Google({ clientId: googleId, clientSecret: googleSecret })] : [],
    secret,
} satisfies NextAuthConfig;
