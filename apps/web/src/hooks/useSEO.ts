import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { SITE_CONFIG } from '../config/site';

interface SEOProps {
  titleKey?: string;
  descriptionKey?: string;
  path?: string;
  lang?: string;
}

export function useSEO({ titleKey = 'meta.title', descriptionKey = 'meta.description', path = '', lang }: SEOProps = {}) {
  const { t, i18n } = useTranslation('common');
  const currentLang = lang || i18n.language || 'en';
  const title = t(titleKey);
  const description = t(descriptionKey);
  const siteUrl = SITE_CONFIG.siteUrl;
  const canonical = `${siteUrl}/${currentLang}${path ? `/${path}` : ''}`;
  const ogImage = `${siteUrl}${SITE_CONFIG.defaultOgImage}`;

  useEffect(() => {
    document.title = title;
    document.documentElement.lang = currentLang;

    setMeta('description', description);
    setMeta('og:title', title);
    setMeta('og:description', description);
    setMeta('og:url', canonical);
    setMeta('og:type', 'website');
    setMeta('og:image', ogImage);
    setMeta('twitter:card', 'summary_large_image');
    setMeta('twitter:title', title);
    setMeta('twitter:description', description);
    setMeta('twitter:image', ogImage);

    if (SITE_CONFIG.enableCanonical) {
      setLink('canonical', canonical);
      for (const lng of ['en', 'vi', 'ja']) {
        setHreflang(lng, `${siteUrl}/${lng}${path ? `/${path}` : ''}`);
      }
      setHreflang('x-default', `${siteUrl}/en${path ? `/${path}` : ''}`);
    } else {
      removeLink('canonical');
      for (const lng of ['en', 'vi', 'ja', 'x-default']) {
        removeHreflang(lng);
      }
    }
  }, [title, description, canonical, currentLang, path, siteUrl, ogImage]);
}

function setMeta(nameOrProperty: string, content: string) {
  const isOg = nameOrProperty.startsWith('og:') || nameOrProperty.startsWith('twitter:');
  const attr = isOg ? 'property' : 'name';
  let el = document.querySelector(`meta[${attr}="${nameOrProperty}"]`) as HTMLMetaElement | null;
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, nameOrProperty);
    document.head.appendChild(el);
  }
  el.content = content;
}

function setLink(rel: string, href: string) {
  let el = document.querySelector(`link[rel="${rel}"]`) as HTMLLinkElement | null;
  if (!el) {
    el = document.createElement('link');
    el.rel = rel;
    document.head.appendChild(el);
  }
  el.href = href;
}

function removeLink(rel: string) {
  const el = document.querySelector(`link[rel="${rel}"]`);
  if (el && el.parentNode) {
    el.parentNode.removeChild(el);
  }
}

function setHreflang(lang: string, href: string) {
  let el = document.querySelector(`link[rel="alternate"][hreflang="${lang}"]`) as HTMLLinkElement | null;
  if (!el) {
    el = document.createElement('link');
    el.rel = 'alternate';
    el.hreflang = lang;
    document.head.appendChild(el);
  }
  el.href = href;
}

function removeHreflang(lang: string) {
  const el = document.querySelector(`link[rel="alternate"][hreflang="${lang}"]`);
  if (el && el.parentNode) {
    el.parentNode.removeChild(el);
  }
}
