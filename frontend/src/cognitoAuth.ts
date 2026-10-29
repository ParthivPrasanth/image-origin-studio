/** Browser-only authorization-code + PKCE flow for a public Cognito app client. */

export type CognitoPublicConfig = {
  client_id: string;
  domain: string;
};

type PendingLogin = {
  state: string;
  verifier: string;
  startedAt: number;
  returnHash: string;
};

type StoredSession = {
  accessToken: string;
  expiresAt: number;
};

const PENDING_KEY = "ios_cognito_pending";
const SESSION_KEY = "ios_cognito_session";
let callbackAttempt: Promise<string | null> | null = null;

function callbackUrl() {
  return `${window.location.origin}/`;
}

function randomBase64Url(bytes: number) {
  const value = new Uint8Array(bytes);
  crypto.getRandomValues(value);
  return btoa(String.fromCharCode(...value))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
}

function base64Url(bytes: Uint8Array) {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
}

export async function beginCognitoLogin(config: CognitoPublicConfig) {
  const verifier = randomBase64Url(48);
  const state = randomBase64Url(24);
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(verifier),
  );
  const pending: PendingLogin = {
    state,
    verifier,
    startedAt: Date.now(),
    returnHash: window.location.hash || "#history",
  };
  sessionStorage.setItem(PENDING_KEY, JSON.stringify(pending));
  const url = new URL("/oauth2/authorize", config.domain);
  url.search = new URLSearchParams({
    response_type: "code",
    client_id: config.client_id,
    redirect_uri: callbackUrl(),
    scope: "openid",
    state,
    code_challenge_method: "S256",
    code_challenge: base64Url(new Uint8Array(digest)),
  }).toString();
  window.location.assign(url.href);
}

export function currentCognitoToken(): string | null {
  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const session = JSON.parse(raw) as StoredSession;
    if (
      typeof session.accessToken === "string" &&
      session.accessToken &&
      typeof session.expiresAt === "number" &&
      session.expiresAt > Date.now() + 30_000
    ) {
      return session.accessToken;
    }
  } catch {
    // Invalid or stale sessions must not be sent to the API.
  }
  sessionStorage.removeItem(SESSION_KEY);
  return null;
}

async function exchangeCognitoCode(
  config: CognitoPublicConfig,
): Promise<string | null> {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  const error = params.get("error");
  if (!code && !error) return null;
  const raw = sessionStorage.getItem(PENDING_KEY);
  sessionStorage.removeItem(PENDING_KEY);
  const cleanUrl = `${callbackUrl()}${window.location.hash}`;
  window.history.replaceState(null, "", cleanUrl);
  if (error)
    throw new Error("Sign-in was cancelled or could not be completed.");
  let pending: PendingLogin;
  try {
    pending = JSON.parse(raw || "") as PendingLogin;
  } catch {
    throw new Error("The sign-in attempt expired. Please try again.");
  }
  if (
    !pending ||
    pending.state !== params.get("state") ||
    typeof pending.verifier !== "string" ||
    pending.verifier.length < 43 ||
    typeof pending.startedAt !== "number" ||
    Date.now() - pending.startedAt > 10 * 60_000 ||
    pending.startedAt > Date.now() + 30_000
  ) {
    throw new Error("The sign-in response did not match this browser session.");
  }
  const response = await fetch(new URL("/oauth2/token", config.domain), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config.client_id,
      code: code || "",
      code_verifier: pending.verifier,
      redirect_uri: callbackUrl(),
    }),
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Sign-in could not be completed.");
  const body: unknown = await response.json();
  if (
    !body ||
    typeof body !== "object" ||
    !("access_token" in body) ||
    typeof body.access_token !== "string" ||
    !("expires_in" in body) ||
    typeof body.expires_in !== "number" ||
    body.expires_in <= 0 ||
    !("token_type" in body) ||
    body.token_type !== "Bearer"
  ) {
    throw new Error("Sign-in returned an invalid session.");
  }
  const session: StoredSession = {
    accessToken: body.access_token,
    expiresAt: Date.now() + body.expires_in * 1000,
  };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  if (pending.returnHash) window.location.hash = pending.returnHash;
  return session.accessToken;
}

export function completeCognitoLogin(
  config: CognitoPublicConfig,
): Promise<string | null> {
  callbackAttempt ??= exchangeCognitoCode(config);
  return callbackAttempt;
}

export function clearCognitoSession() {
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(PENDING_KEY);
}

export function cognitoLogoutUrl(config: CognitoPublicConfig) {
  const url = new URL("/logout", config.domain);
  url.search = new URLSearchParams({
    client_id: config.client_id,
    logout_uri: callbackUrl(),
  }).toString();
  return url.href;
}
