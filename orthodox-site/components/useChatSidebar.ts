"use client";

import { useEffect, useState } from "react";

/** The visitor's choice to show or hide the past-chats sidebar on desktop (UI-025). */
const STORAGE_KEY = "learn-orthodoxy-chats-sidebar";

/**
 * The past-chats sidebar shared by the home and chat pages (UI-025).
 *
 * - Desktop: a column that is open by default once the visitor has chats. The header's toggle
 *   ("chat:toggleSidebar") hides and shows it, and the choice is remembered in this browser.
 * - Phone: a drawer opened by the header's menu button ("chat:openSidebar").
 *
 * The page tells the header whether there is a sidebar to toggle and whether it is open
 * ("chat:sidebarState"), and answers again when the header asks ("chat:requestSidebarState").
 */
export function useChatSidebar(hasChats: boolean) {
  // Read once, on the first client render. The server renders "open"; that is safe because the
  // column only shows once the chats have loaded, after hydration.
  const [open, setOpen] = useState(() => {
    if (typeof window === "undefined") return true;
    try {
      return window.localStorage.getItem(STORAGE_KEY) !== "closed";
    } catch {
      return true; // Storage can be unavailable (private windows, blocked site data).
    }
  });
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const toggle = () =>
      setOpen((previous) => {
        const next = !previous;
        try {
          window.localStorage.setItem(STORAGE_KEY, next ? "open" : "closed");
        } catch {
          // Not remembered this time; the sidebar still toggles.
        }
        return next;
      });
    const openDrawer = () => setMobileOpen(true);
    window.addEventListener("chat:toggleSidebar", toggle);
    window.addEventListener("chat:openSidebar", openDrawer);
    return () => {
      window.removeEventListener("chat:toggleSidebar", toggle);
      window.removeEventListener("chat:openSidebar", openDrawer);
    };
  }, []);

  useEffect(() => {
    const announce = () =>
      window.dispatchEvent(new CustomEvent("chat:sidebarState", { detail: { available: hasChats, open } }));
    announce();
    window.addEventListener("chat:requestSidebarState", announce);
    return () => {
      window.removeEventListener("chat:requestSidebarState", announce);
      window.dispatchEvent(new CustomEvent("chat:sidebarState", { detail: { available: false, open } }));
    };
  }, [hasChats, open]);

  // The phone drawer covers the page: the page underneath doesn't scroll while it is open.
  useEffect(() => {
    if (!mobileOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [mobileOpen]);

  return {
    /** The desktop column is shown: the visitor has chats and hasn't hidden it. */
    visible: hasChats && open,
    mobileOpen,
    setMobileOpen,
  };
}
