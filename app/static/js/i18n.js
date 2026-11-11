/* Finora — internationalization */
class I18n {
  constructor() {
    this.lang = "ru";
    this.translations = {};
    this.fallback = "en";
  }

  async load(lang) {
    try {
      const res = await fetch(`/static/js/locales/${lang}.json`, { cache: "no-store" });
      if (!res.ok) throw new Error(`locale ${lang} not found`);
      this.translations[lang] = await res.json();
    } catch (e) {
      console.warn(e);
    }
    try {
      const res = await fetch(`/static/js/locales/${this.fallback}.json`, { cache: "no-store" });
      if (res.ok) this.translations[this.fallback] = await res.json();
    } catch (e) {}
    this.lang = lang;
  }

  t(key) {
    let value = this.translations[this.lang]?.[key];
    if (value === undefined) value = this.translations[this.fallback]?.[key];
    if (value === undefined) return key;
    return value;
  }

  translateNode(node) {
    const key = node.getAttribute("data-i18n");
    if (key) {
      const text = this.t(key);
      if (node.tagName === "INPUT" || node.tagName === "TEXTAREA") {
        if (!node.value) node.placeholder = text;
      } else {
        node.textContent = text;
      }
    }
    const labelKey = node.getAttribute("data-i18n-label");
    if (labelKey) {
      node.title = this.t(labelKey);
      node.setAttribute("aria-label", this.t(labelKey));
    }
    const placeholderKey = node.getAttribute("data-i18n-placeholder");
    if (placeholderKey) {
      node.placeholder = this.t(placeholderKey);
    }
  }

  translateRoot(root = document) {
    root.querySelectorAll("[data-i18n], [data-i18n-label], [data-i18n-placeholder]").forEach((n) => this.translateNode(n));
    // translate root itself if it carries a key
    if (root.hasAttribute && root.hasAttribute("data-i18n")) this.translateNode(root);
  }
}

window.i18n = new I18n();
