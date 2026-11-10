"use client";
import { useEffect, useState } from "react";
import { getProviders } from "next-auth/react";

// True once the server reports that the Google provider is configured.
export function useAuthEnabled(): boolean {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    let active = true;
    getProviders()
      .then((providers) => active && setEnabled(Boolean(providers?.google)))
      .catch(() => active && setEnabled(false));
    return () => {
      active = false;
    };
  }, []);
  return enabled;
}
