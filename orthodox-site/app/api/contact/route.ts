import { NextResponse } from "next/server";

export const runtime = "nodejs";

const DEFAULT_SUBJECT = "Learn Orthodoxy Contact";
const MIN_SUBMIT_MS = 3500;
const RATE_LIMIT_WINDOW_MS = 10 * 60 * 1000;
const RATE_LIMIT_MAX = 5;

const rateLimitStore = new Map<string, { count: number; resetAt: number }>();

type ContactPayload = {
  name?: string;
  email?: string;
  subject?: string;
  message?: string;
  company?: string;
  startedAt?: number;
  captchaToken?: string;
};

class ContactConfigError extends Error {
  status = 500;

  constructor(public code: string, message: string) {
    super(message);
  }
}

class EmailProviderError extends Error {
  status = 502;

  constructor(
    message: string,
    public resendStatus?: number,
    public resendMessage?: string
  ) {
    super(message);
  }
}

function logContactFailure(
  event: string,
  details: {
    status: number;
    reason: string;
    ip?: string;
    resendStatus?: number;
    resendMessage?: string;
    recipientCount?: number;
    fromEmail?: string;
  }
) {
  console.warn(event, details);
}

function contactError(error: string, message: string, status: number) {
  return NextResponse.json({ error, message }, { status });
}

function getClientIp(request: Request) {
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) return forwardedFor.split(",")[0]?.trim() || "unknown";
  return (
    request.headers.get("x-real-ip") ||
    request.headers.get("cf-connecting-ip") ||
    "unknown"
  );
}

function isLocalRequest(request: Request, ip: string) {
  const hostname = new URL(request.url).hostname;
  return hostname === "localhost" || hostname === "127.0.0.1" || ip === "::1" || ip === "127.0.0.1";
}

function isRateLimited(ip: string) {
  const now = Date.now();
  const entry = rateLimitStore.get(ip);

  return Boolean(entry && entry.resetAt > now && entry.count >= RATE_LIMIT_MAX);
}

function recordSuccessfulSubmission(ip: string) {
  const now = Date.now();
  const entry = rateLimitStore.get(ip);

  if (!entry || entry.resetAt <= now) {
    rateLimitStore.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return;
  }
  entry.count += 1;
}

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function countLinks(value: string) {
  const matches = value.match(/https?:\/\/|www\.|\.com\b|\.net\b|\.org\b/gi);
  return matches?.length || 0;
}

function hasSpamKeywords(value: string) {
  return /\b(?:crypto|forex|binary options|loan offer|seo services|guest post|backlinks|casino|viagra|investment opportunity|whatsapp|telegram)\b/i.test(
    value
  );
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function plainTextToHtml(value: string) {
  return escapeHtml(value).replace(/\r?\n/g, "<br />");
}

function configuredRecipients() {
  const configured = process.env.CONTACT_TO_EMAILS?.split(",")
    .map((email) => email.trim())
    .filter(Boolean);
  if (!configured?.length) {
    throw new ContactConfigError("contact_recipients_missing", "Contact recipients are not configured.");
  }
  return configured;
}

function contactEmailConfig() {
  const apiKey = process.env.RESEND_API_KEY;
  const from = process.env.CONTACT_FROM_EMAIL;

  if (!apiKey) {
    throw new ContactConfigError("resend_api_key_missing", "Email service is not configured.");
  }

  if (!from) {
    throw new ContactConfigError("contact_from_missing", "Contact sender email is not configured.");
  }

  return {
    apiKey,
    from,
    to: configuredRecipients(),
  };
}

async function verifyTurnstile(token: string, ip: string) {
  const secret = process.env.TURNSTILE_SECRET_KEY;
  if (!secret) return { ok: true };
  if (!token) return { ok: false, reason: "missing_token" };

  const body = new URLSearchParams({
    secret,
    response: token,
  });

  if (ip !== "unknown") {
    body.set("remoteip", ip);
  }

  const response = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
    method: "POST",
    body,
    cache: "no-store",
  });

  if (!response.ok) {
    return { ok: false, reason: `turnstile_http_${response.status}` };
  }
  const result = (await response.json()) as { success?: boolean; "error-codes"?: string[] };
  return {
    ok: Boolean(result.success),
    reason: result.success ? undefined : result["error-codes"]?.join(",") || "turnstile_rejected",
  };
}

async function sendContactEmail({
  name,
  email,
  subject,
  message,
  ip,
  userAgent,
}: {
  name: string;
  email: string;
  subject: string;
  message: string;
  ip: string;
  userAgent: string;
}) {
  const { apiKey, from, to } = contactEmailConfig();

  const timestamp = new Date().toISOString();
  const safeSubject = subject || DEFAULT_SUBJECT;
  const html = `
    <h2>Learn Orthodoxy Contact</h2>
    <p><strong>Name:</strong> ${escapeHtml(name)}</p>
    <p><strong>Email:</strong> ${escapeHtml(email)}</p>
    <p><strong>Subject:</strong> ${escapeHtml(safeSubject)}</p>
    <p><strong>Timestamp:</strong> ${escapeHtml(timestamp)}</p>
    <p><strong>IP:</strong> ${escapeHtml(ip)}</p>
    <p><strong>User Agent:</strong> ${escapeHtml(userAgent)}</p>
    <hr />
    <p>${plainTextToHtml(message)}</p>
  `;

  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from,
      to,
      reply_to: email,
      subject: safeSubject,
      text: [
        "Learn Orthodoxy Contact",
        `Name: ${name}`,
        `Email: ${email}`,
        `Subject: ${safeSubject}`,
        `Timestamp: ${timestamp}`,
        `IP: ${ip}`,
        `User Agent: ${userAgent}`,
        "",
        message,
      ].join("\n"),
      html,
    }),
    cache: "no-store",
  });

  if (!response.ok) {
    const rawError = await response.text().catch(() => "");
    let resendMessage = rawError;
    try {
      const data = JSON.parse(rawError) as { message?: string; error?: string };
      resendMessage = data.message || data.error || rawError;
    } catch {
      resendMessage = rawError;
    }

    throw new EmailProviderError(
      "The email service could not send the message.",
      response.status,
      resendMessage || "Resend request failed."
    );
  }

  return {
    recipientCount: to.length,
    fromEmail: from,
  };
}

export async function POST(request: Request) {
  const ip = getClientIp(request);
  const userAgent = request.headers.get("user-agent") || "unknown";
  const localRequest = isLocalRequest(request, ip);

  try {
    const payload = (await request.json().catch(() => ({}))) as ContactPayload;
    const name = (payload.name || "").trim();
    const email = (payload.email || "").trim();
    const subject = (payload.subject || DEFAULT_SUBJECT).trim() || DEFAULT_SUBJECT;
    const message = (payload.message || "").trim();
    const honeypot = (payload.company || "").trim();
    const startedAt = Number(payload.startedAt || 0);
    const captchaToken = (payload.captchaToken || "").trim();

    if (honeypot) {
      logContactFailure("CONTACT_VALIDATION_FAILED", { status: 400, reason: "honeypot_filled", ip });
      return contactError("validation_failed", "Unable to send message.", 400);
    }

    if (!startedAt || Date.now() - startedAt < MIN_SUBMIT_MS) {
      logContactFailure("CONTACT_VALIDATION_FAILED", { status: 400, reason: "submitted_too_fast", ip });
      return contactError("validation_failed", "Please take a little more time before sending.", 400);
    }

    if (!name || name.length > 120) {
      logContactFailure("CONTACT_VALIDATION_FAILED", { status: 400, reason: "invalid_name", ip });
      return contactError("validation_failed", "Please enter your name.", 400);
    }

    if (!isValidEmail(email) || email.length > 254) {
      logContactFailure("CONTACT_VALIDATION_FAILED", { status: 400, reason: "invalid_email", ip });
      return contactError("validation_failed", "Please enter a valid email address.", 400);
    }

    if (subject.length > 160) {
      logContactFailure("CONTACT_VALIDATION_FAILED", { status: 400, reason: "subject_too_long", ip });
      return contactError("validation_failed", "Please shorten the subject.", 400);
    }

    if (message.length < 10 || message.length > 3000) {
      logContactFailure("CONTACT_VALIDATION_FAILED", { status: 400, reason: "message_length", ip });
      return contactError("validation_failed", "Message must be between 10 and 3000 characters.", 400);
    }

    if (countLinks(message) > 2 || hasSpamKeywords(`${subject}\n${message}`)) {
      logContactFailure("CONTACT_VALIDATION_FAILED", { status: 400, reason: "spam_filter", ip });
      return contactError("validation_failed", "Message could not be accepted.", 400);
    }

    const captcha = await verifyTurnstile(captchaToken, ip);
    if (!captcha.ok) {
      logContactFailure("CONTACT_CAPTCHA_FAILED", {
        status: 400,
        reason: captcha.reason || "captcha_failed",
        ip,
      });
      return contactError("captcha_failed", "Captcha verification failed. Please try again.", 400);
    }

    if (process.env.NODE_ENV === "production" && !process.env.TURNSTILE_SECRET_KEY) {
      console.warn("Contact form captcha is not configured. Set TURNSTILE_SECRET_KEY in Vercel.");
    }

    contactEmailConfig();

    if (!localRequest && isRateLimited(ip)) {
      logContactFailure("CONTACT_RATE_LIMITED", { status: 429, reason: "rate_limit_exceeded", ip });
      return contactError("rate_limited", "Too many messages. Please wait a few minutes and try again.", 429);
    }

    const result = await sendContactEmail({ name, email, subject, message, ip, userAgent });
    if (!localRequest) {
      recordSuccessfulSubmission(ip);
    }
    console.log("CONTACT_SUCCESS", {
      status: 200,
      recipientCount: result.recipientCount,
      fromEmail: result.fromEmail,
    });
    return NextResponse.json({ ok: true });
  } catch (error) {
    if (error instanceof ContactConfigError) {
      logContactFailure("CONTACT_RESEND_FAILED", {
        status: error.status,
        reason: error.code,
        ip,
        recipientCount: process.env.CONTACT_TO_EMAILS?.split(",").filter(Boolean).length || 0,
        fromEmail: process.env.CONTACT_FROM_EMAIL || "",
      });
      return contactError("configuration_error", error.message, error.status);
    }

    if (error instanceof EmailProviderError) {
      logContactFailure("CONTACT_RESEND_FAILED", {
        status: error.status,
        reason: "resend_rejected",
        ip,
        resendStatus: error.resendStatus,
        resendMessage: error.resendMessage,
        recipientCount: process.env.CONTACT_TO_EMAILS?.split(",").filter(Boolean).length || 0,
        fromEmail: process.env.CONTACT_FROM_EMAIL || "",
      });
      return contactError("email_failed", "The email service could not send the message.", error.status);
    }

    logContactFailure("CONTACT_RESEND_FAILED", {
      status: 500,
      reason: error instanceof Error ? error.message : "unknown_error",
      ip,
      recipientCount: process.env.CONTACT_TO_EMAILS?.split(",").filter(Boolean).length || 0,
      fromEmail: process.env.CONTACT_FROM_EMAIL || "",
    });
    return contactError("email_failed", "Unable to send message right now.", 500);
  }
}
