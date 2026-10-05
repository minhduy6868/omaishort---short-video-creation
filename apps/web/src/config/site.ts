/**
 * Central site configuration for omaishort landing page.
 * Flexible domain resolution & SEO options.
 */

export const SITE_CONFIG = {
  /** Default fallback domain if env vars are missing */
  defaultDomain: 'https://omaishort.com',

  /** Resolves current site URL from env vars or fallback */
  get siteUrl(): string {
    const envUrl =
      import.meta.env.VITE_SITE_URL ||
      (import.meta as any).env?.NEXT_PUBLIC_SITE_URL;
    return (envUrl || this.defaultDomain).replace(/\/$/, '');
  },

  /**
   * Flag indicating whether canonical URLs and hreflang tags should be emitted.
   * If domain is an unconfirmed placeholder on staging/preview, set VITE_ENABLE_CANONICAL=false.
   */
  get enableCanonical(): boolean {
    return import.meta.env.VITE_ENABLE_CANONICAL !== 'false';
  },

  defaultOgImage: '/og-image.png',
};
