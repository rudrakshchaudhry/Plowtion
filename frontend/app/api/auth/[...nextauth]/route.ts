import { NextResponse } from "next/server";
import { handlers } from "@/auth";
import { authEnabled } from "@/auth.config";

// When Google sign-in is not configured, answer the client's session/providers
// requests with empty objects (= "no session", "no providers") instead of errors.
const disabled = () => NextResponse.json({});

export const GET = authEnabled ? handlers.GET : disabled;
export const POST = authEnabled ? handlers.POST : disabled;
