import { NextResponse } from "next/server";

export const runtime = "nodejs";

const DEFAULT_TO_EMAILS = ["johnazer07@gmail.com", "frjeromemaximous@gmail.com"];
const DEFAULT_SUBJECT = "Learn Orthodoxy Contact";
const MIN_SUBMIT_MS = 3500;
const RATE_LIMIT_WINDOW_MS = 15 * 60 * 1000;
const RATE_LIMIT_MAX = 4;

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

function getClientIp(request: Request) {
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) return forwardedFor.split(",")[0]?.trim() || "unknown";
  return (
    request.headers.get("x-real-ip") ||
    request.headers.get("cf-connecting-ip") ||
    "unknown"
  );
}

function isRateLimited(ip: string) {
  const now = Date.now();
  const entry = rateLimitStore.get(ip);

  if (!entry || entry.resetAt <= now) {
    rateLimitStore.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return false;
  }

  entry.count += 1;
  return entry.count > RATE_LIMIT_MAX;
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
  return configured?.length ? configured : DEFAULT_TO_EMAILS;
}

async function verifyTurnstile(token: string, ip: string) {
  const secret = process.env.TURNSTILE_SECRET_KEY;
  if (!secret) return true;
  if (!token) return false;

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

  if (!response.ok) return false;
  const result = (await response.json()) as { success?: boolean };
  return Boolean(result.success);
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
  const apiKey = process.env.RESEND_API_KEY;
  const from = process.env.CONTACT_FROM_EMAIL;
  const to = configuredRecipients();

  if (!apiKey || !from) {
    throw new Error("Contact email is not configured.");
  }

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
    throw new Error("Unable to send contact email.");
  }
}

export async function POST(request: Request) {
  const ip = getClientIp(request);
  const userAgent = request.headers.get("user-agent") || "unknown";

  try {
    if (isRateLimited(ip)) {
      return NextResponse.json({ error: "Too many messages. Please try again later." }, { status: 429 });
    }

    const payload = (await request.json().catch(() => ({}))) as ContactPayload;
    const name = (payload.name || "").trim();
    const email = (payload.email || "").trim();
    const subject = (payload.subject || DEFAULT_SUBJECT).trim() || DEFAULT_SUBJECT;
    const message = (payload.message || "").trim();
    const honeypot = (payload.company || "").trim();
    const startedAt = Number(payload.startedAt || 0);
    const captchaToken = (payload.captchaToken || "").trim();

    if (honeypot) {
      return NextResponse.json({ error: "Unable to send message." }, { status: 400 });
    }

    if (!startedAt || Date.now() - startedAt < MIN_SUBMIT_MS) {
      return NextResponse.json({ error: "Please take a little more time before sending." }, { status: 400 });
    }

    if (!name || name.length > 120) {
      return NextResponse.json({ error: "Please enter your name." }, { status: 400 });
    }

    if (!isValidEmail(email) || email.length > 254) {
      return NextResponse.json({ error: "Please enter a valid email address." }, { status: 400 });
    }

    if (subject.length > 160) {
      return NextResponse.json({ error: "Please shorten the subject." }, { status: 400 });
    }

    if (message.length < 10 || message.length > 3000) {
      return NextResponse.json(
        { error: "Message must be between 10 and 3000 characters." },
        { status: 400 }
      );
    }

    if (countLinks(message) > 2 || hasSpamKeywords(`${subject}\n${message}`)) {
      return NextResponse.json({ error: "Message could not be accepted." }, { status: 400 });
    }

    const captchaOk = await verifyTurnstile(captchaToken, ip);
    if (!captchaOk) {
      return NextResponse.json({ error: "Captcha verification failed." }, { status: 400 });
    }

    if (process.env.NODE_ENV === "production" && !process.env.TURNSTILE_SECRET_KEY) {
      console.warn("Contact form captcha is not configured. Set TURNSTILE_SECRET_KEY in Vercel.");
    }

    await sendContactEmail({ name, email, subject, message, ip, userAgent });
    return NextResponse.json({ ok: true });
  } catch (error) {
    const message =
      error instanceof Error && error.message === "Contact email is not configured."
        ? error.message
        : "Unable to send message right now.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
