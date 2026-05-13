"use client";

import Script from "next/script";
import { FormEvent, useMemo, useState } from "react";

const DEFAULT_SUBJECT = "Learn Orthodoxy Contact";
const turnstileSiteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "";

type SubmitState = {
  status: "idle" | "sending" | "success" | "error";
  message: string;
};

export default function ContactPage() {
  const [startedAt] = useState(() => Date.now());
  const [subject, setSubject] = useState(DEFAULT_SUBJECT);
  const [state, setState] = useState<SubmitState>({ status: "idle", message: "" });
  const isSending = state.status === "sending";
  const captchaEnabled = Boolean(turnstileSiteKey);

  const statusClassName = useMemo(() => {
    if (state.status === "success") return "contact-status contact-status-success";
    if (state.status === "error") return "contact-status contact-status-error";
    return "contact-status";
  }, [state.status]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSending) return;

    const form = event.currentTarget;
    const formData = new FormData(form);

    setState({ status: "sending", message: "Sending..." });

    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: String(formData.get("name") || ""),
          email: String(formData.get("email") || ""),
          subject: String(formData.get("subject") || DEFAULT_SUBJECT),
          message: String(formData.get("message") || ""),
          company: String(formData.get("company") || ""),
          captchaToken: String(formData.get("cf-turnstile-response") || ""),
          startedAt,
        }),
      });

      const result = (await response.json().catch(() => ({}))) as { error?: string; message?: string };

      if (!response.ok) {
        setState({
          status: "error",
          message: result.message || result.error || "Unable to send message right now.",
        });
        return;
      }
    } catch {
      setState({
        status: "error",
        message: "Unable to reach the contact service. Please try again.",
      });
      return;
    }

    form.reset();
    setSubject(DEFAULT_SUBJECT);
    setState({ status: "success", message: "Message sent." });
  }

  return (
    <main className="page-shell contact-page">
      {captchaEnabled ? (
        <Script
          src="https://challenges.cloudflare.com/turnstile/v0/api.js"
          async
          defer
          strategy="afterInteractive"
        />
      ) : null}

      <div className="section-heading left contact-heading">
        <h1>Contact</h1>
        <p>
          To ensure we provide precise and accurate faith education, we have restrained our model to reference the
          sources listed on the Credits page. Please contact us with your feedback or questions. We continue to
          fine-tune the model to ensure we provide rich Orthodox Christian faith education.
        </p>
      </div>

      <form className="contact-form" onSubmit={handleSubmit}>
        <div className="contact-field">
          <label htmlFor="contact-name">Name</label>
          <input id="contact-name" name="name" type="text" autoComplete="name" required maxLength={120} />
        </div>

        <div className="contact-field">
          <label htmlFor="contact-email">Email</label>
          <input id="contact-email" name="email" type="email" autoComplete="email" required maxLength={254} />
        </div>

        <div className="contact-field">
          <label htmlFor="contact-subject">Subject</label>
          <input
            id="contact-subject"
            name="subject"
            type="text"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            maxLength={160}
          />
        </div>

        <div className="contact-field">
          <label htmlFor="contact-message">Message</label>
          <textarea
            id="contact-message"
            name="message"
            required
            minLength={10}
            maxLength={3000}
            rows={7}
          />
        </div>

        <div className="contact-honeypot" aria-hidden="true">
          <label htmlFor="contact-company">Company</label>
          <input id="contact-company" name="company" type="text" tabIndex={-1} autoComplete="off" />
        </div>

        {captchaEnabled ? (
          <div className="contact-captcha">
            <div className="cf-turnstile" data-sitekey={turnstileSiteKey} />
          </div>
        ) : null}

        <div className="contact-actions">
          <button type="submit" className="contact-submit" disabled={isSending}>
            {isSending ? "Sending..." : "Send Message"}
          </button>
          {state.message ? <div className={statusClassName}>{state.message}</div> : null}
        </div>
      </form>
    </main>
  );
}
