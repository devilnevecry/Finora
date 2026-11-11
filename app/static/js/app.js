/* Finora — common application logic */

(function () {
  const csrfToken = window.FINORA?.csrfToken || "";
  const langMeta = document.querySelector('meta[name="app-language"]');
  const currentLang = langMeta ? langMeta.content : "ru";

  // Theme handling
  const themeToggle = document.getElementById("theme-toggle");
  const htmlEl = document.documentElement;
  const themeIcon = themeToggle ? themeToggle.querySelector(".theme-icon") : null;

  function loadTheme() {
    const saved = localStorage.getItem("finora_theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = saved || (prefersDark ? "dark" : "light");
    applyTheme(theme);
  }

  function applyTheme(theme) {
    htmlEl.setAttribute("data-theme", theme);
    localStorage.setItem("finora_theme", theme);
    updateThemeIcon(theme);
  }

  function updateThemeIcon(theme) {
    if (!themeIcon) return;
    themeIcon.innerHTML = theme === "dark"
      ? `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/><circle cx="12" cy="12" r="3"/>`
      : `<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>`;
  }

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const next = htmlEl.getAttribute("data-theme") === "light" ? "dark" : "light";
      applyTheme(next);
    });
  }
  loadTheme();

  // Language
  async function initLanguage() {
    await window.i18n.load(currentLang);
    window.i18n.translateRoot(document);
    const langSelector = document.getElementById("lang-selector");
    if (langSelector) langSelector.value = currentLang;
  }
  initLanguage();

  // Mobile drawer
  const mobileMenuToggle = document.getElementById("mobile-menu-toggle");
  const mobileDrawerClose = document.getElementById("mobile-drawer-close");
  const mobileDrawer = document.getElementById("mobile-drawer");
  const overlay = document.getElementById("overlay");
  function toggleDrawer() { mobileDrawer.classList.toggle("open"); overlay.classList.toggle("open"); }
  if (mobileMenuToggle) mobileMenuToggle.addEventListener("click", toggleDrawer);
  if (mobileDrawerClose) mobileDrawerClose.addEventListener("click", toggleDrawer);
  if (overlay) overlay.addEventListener("click", toggleDrawer);

  // Flash dismiss
  document.querySelectorAll(".flash-dismiss").forEach((btn) => {
    btn.addEventListener("click", () => btn.closest(".flash").remove());
  });

  // Toast
  window.showToast = function ({ message, type = "info", duration = 4000 } = {}) {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const el = document.createElement("div");
    el.className = "toast toast-" + type;
    el.innerHTML = `<span>${escapeHtml(message)}</span><button style="background:none;border:none;color:inherit;cursor:pointer;margin-left:auto" aria-label="Закрыть">✕</button>`;
    el.querySelector("button").addEventListener("click", () => el.remove());
    container.appendChild(el);
    setTimeout(() => el.remove(), duration);
  };

  window.showError = function (message) { window.showToast({ message, type: "error" }); };
  window.showSuccess = function (message) { window.showToast({ message, type: "success" }); };

  // CSRF fetch helper
  async function apiFetch(path, { method = "GET", body, headers = {}, formData = false } = {}) {
    const h = { ...headers };
    if (method !== "GET") {
      h["X-CSRF-Token"] = window.FINORA.csrfToken;
    }
    const res = await fetch(path, { method, headers: h, body });
    // Refresh token if the server rotated it.
    const tok = res.headers.get("x-csrf-token");
    if (tok) { window.FINORA.csrfToken = tok; }
    return res;
  }

  window.apiFetch = apiFetch;

  // Generic delete confirmation
  window.confirmDelete = async function ({ message, onConfirm }) {
    const ok = confirm(message || "Удалить запись?");
    if (ok) await onConfirm();
  };

  function escapeHtml(text) {
    const d = document.createElement("div");
    d.textContent = text;
    return d.innerHTML;
  }

  // Format number with grouping
  window.formatNumber = function (n, decimals = 2) {
    return Number(n).toLocaleString(currentLang === "ru" ? "ru-RU" : "en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  // Currency formatting
  window.formatCurrency = function (minorUnits, symbol = "$") {
    const units = Number(minorUnits) / 100;
    const formatted = Math.abs(units).toLocaleString(currentLang === "ru" ? "ru-RU" : "en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    const sign = units < 0 ? "\u2212" : "";
    return currentLang === "ru" ? `${formatted} ${symbol}` : `${sign}${symbol}${formatted}`;
  };

})();
