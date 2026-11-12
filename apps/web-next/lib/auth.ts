// auth.ts — the browser side of the capture network's identity.
//
// The console used to live in a static file (public/console/console.js) that
// the Next app could not reach. This module is the same ceremony, written for
// the Next client components: passkey sign-up, passkey sign-in, OAuth
// providers, and the session token the API expects as `Authorization: Bearer`.
//
// House rules (same as lib/social.ts):
//   · the token lives in localStorage under TOKEN_KEY — the API is
//     cookie-less, so there is no session to ride on and no CSRF surface.
//   · every failure surfaces the API's own `detail` verbatim.
//   · nothing here re-implements the server: it only speaks WebAuthn.

import { API_BASE, getToken, setToken, type ApiResult } from "./social";

// ------------------------------------------------------------------ storage

// ------------------------------------------------------------------- base64

function b64urlToBytes(value: string): Uint8Array {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded.padEnd(Math.ceil(padded.length / 4) * 4, "="));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

function bytesToB64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// ------------------------------------------------------------------ webauthn

type PublicKeyOptions = {
  challenge: string;
  rp?: { id?: string; name?: string };
  user?: { id: string; name: string; displayName?: string };
  pubKeyCredParams?: Array<{ type: string; alg: number }>;
  timeout?: number;
  authenticatorSelection?: Record<string, unknown>;
  excludeCredentials?: Array<{ id: string; type: string }>;
  allowCredentials?: Array<{ id: string; type: string }>;
};

function toPublicKey(options: PublicKeyOptions): PublicKeyCredentialCreationOptions {
  const user = options.user
    ? { ...options.user, id: b64urlToBytes(options.user.id) as unknown as string }
    : undefined;
  const excludeCredentials = (options.excludeCredentials ?? []).map((descriptor) => ({
    ...descriptor,
    id: b64urlToBytes(descriptor.id) as unknown as string,
  }));
  const allowCredentials = (options.allowCredentials ?? []).map((descriptor) => ({
    ...descriptor,
    id: b64urlToBytes(descriptor.id) as unknown as string,
  }));

  const pk = {
    ...options,
    challenge: b64urlToBytes(options.challenge) as unknown as string,
    ...(user ? { user } : {}),
    ...(excludeCredentials.length ? { excludeCredentials } : {}),
    ...(allowCredentials.length ? { allowCredentials } : {}),
  };
  return pk as unknown as PublicKeyCredentialCreationOptions;
}

function serializeCreation(credential: PublicKeyCredential): Record<string, unknown> {
  const response = credential.response as AuthenticatorAttestationResponse;
  return {
    id: credential.id,
    rawId: bytesToB64url(credential.rawId),
    type: credential.type,
    response: {
      attestationObject: bytesToB64url(response.attestationObject),
      clientDataJSON: bytesToB64url(response.clientDataJSON),
    },
  };
}

function serializeAssertion(assertion: PublicKeyCredential): Record<string, unknown> {
  const response = assertion.response as AuthenticatorAssertionResponse;
  return {
    id: assertion.id,
    rawId: bytesToB64url(assertion.rawId),
    type: assertion.type,
    response: {
      authenticatorData: bytesToB64url(response.authenticatorData),
      clientDataJSON: bytesToB64url(response.clientDataJSON),
      signature: bytesToB64url(response.signature),
      userHandle: response.userHandle ? bytesToB64url(response.userHandle) : null,
    },
  };
}

async function postJson<T>(path: string, body: unknown): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    const reason = err instanceof Error ? err.message : "unknown";
    return { ok: false, status: 0, data: null, detail: `Network error: ${reason}` };
  }
  const text = await res.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!res.ok) {
    const detail =
      payload && typeof payload === "object" && typeof (payload as { detail?: unknown }).detail === "string"
        ? ((payload as { detail: string }).detail)
        : `HTTP ${res.status}`;
    return { ok: false, status: res.status, data: null, detail };
  }
  return { ok: true, status: res.status, data: payload as T, detail: null };
}

// ----------------------------------------------------------------- ceremonies

export function passkeySupported(): boolean {
  return typeof window !== "undefined" && typeof window.PublicKeyCredential !== "undefined";
}

export type AuthResult = { ok: true; handle: string } | { ok: false; detail: string };

/**
 * Create the account and enrol a passkey. The API answers 201 WITHOUT a
 * token on registration (the ceremony proves the key, not a session), so the
 * caller signs in right after.
 */
export async function registerPasskey(handle: string): Promise<AuthResult> {
  if (!passkeySupported()) {
    return { ok: false, detail: "This browser has no passkey support (PublicKeyCredential missing)." };
  }
  const normalized = handle.trim().toLowerCase();
  const options = await postJson<{ options: PublicKeyOptions }>(
    "/v1/auth/passkey/register/options",
    { handle: normalized },
  );
  if (!options.ok || !options.data) {
    return { ok: false, detail: options.detail ?? "Could not start the sign-up ceremony." };
  }
  let credential: PublicKeyCredential | null = null;
  try {
    credential = (await navigator.credentials.create({
      publicKey: toPublicKey(options.data.options),
    })) as PublicKeyCredential | null;
  } catch (err) {
    const reason = err instanceof Error ? err.message : "the browser refused the credential";
    return { ok: false, detail: reason };
  }
  if (!credential) return { ok: false, detail: "The browser returned no credential." };
  const verified = await postJson<unknown>("/v1/auth/passkey/register/verify", {
    handle: normalized,
    credential: serializeCreation(credential),
  });
  if (!verified.ok) return { ok: false, detail: verified.detail ?? "The passkey could not be verified." };
  return { ok: true, handle: normalized };
}

export async function loginPasskey(handle: string): Promise<AuthResult> {
  if (!passkeySupported()) {
    return { ok: false, detail: "This browser has no passkey support (PublicKeyCredential missing)." };
  }
  const normalized = handle.trim().toLowerCase();
  const options = await postJson<{ options: PublicKeyOptions }>(
    "/v1/auth/passkey/login/options",
    { handle: normalized },
  );
  if (!options.ok || !options.data) {
    return { ok: false, detail: options.detail ?? "Could not start the sign-in ceremony." };
  }
  let assertion: PublicKeyCredential | null = null;
  try {
    assertion = (await navigator.credentials.get({
      publicKey: toPublicKey(options.data.options),
    })) as PublicKeyCredential | null;
  } catch (err) {
    const reason = err instanceof Error ? err.message : "the browser refused the credential";
    return { ok: false, detail: reason };
  }
  if (!assertion) return { ok: false, detail: "The browser returned no credential." };
  const verified = await postJson<{ access_token: string }>("/v1/auth/passkey/login/verify", {
    handle: normalized,
    credential: serializeAssertion(assertion),
  });
  if (!verified.ok || !verified.data) {
    return { ok: false, detail: verified.detail ?? "The passkey could not be verified." };
  }
  setToken(verified.data.access_token);
  return { ok: true, handle: normalized };
}

/**
 * OAuth begins at the API, which redirects to the provider and sends the
 * browser back with the token in the URL fragment. The fragment never reaches
 * a server — the client picks it up and stores it.
 */
export function beginOAuth(provider: "github" | "huggingface"): void {
  if (typeof window === "undefined") return;
  const redirect = `${window.location.origin}/console`;
  const url = `${API_BASE}/v1/auth/oauth/${provider}/begin?redirect_uri=${encodeURIComponent(redirect)}`;
  window.location.assign(url);
}

/**
 * Read the token the OAuth callback left in the fragment, then clean the URL
 * so a refresh does not re-run the sign-in.
 */
export function consumeOAuthFragment(): boolean {
  if (typeof window === "undefined") return false;
  const raw = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
  if (!raw) return false;
  const params = new URLSearchParams(raw);
  const token = params.get("auth_token");
  const error = params.get("auth_error");
  if (token) {
    setToken(token);
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    return true;
  }
  if (error) {
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    throw new Error(error);
  }
  return false;
}

export type SessionInfo = {
  handle: string;
  display_name?: string | null;
  token_kind?: string | null;
  expires_at?: string | null;
  reputation?: { points?: number | null; tier?: string | null } | null;
};

/** Who the stored token belongs to, or null when there is no live session. */
export async function fetchSession(): Promise<SessionInfo | null> {
  const token = getToken();
  if (!token) return null;
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/v1/auth/session`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    return null;
  }
  if (!res.ok) return null;
  try {
    const payload = (await res.json()) as Partial<SessionInfo>;
    return typeof payload.handle === "string" ? (payload as SessionInfo) : null;
  } catch {
    return null;
  }
}
