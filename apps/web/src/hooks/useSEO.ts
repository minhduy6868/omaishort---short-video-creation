import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { SITE_CONFIG } from '../config/site';

interface SEOProps {
  titleKey?: string;
  descriptionKey?: string;
  path?: string;
  lang?: string;
  noindex?: boolean;
}

const LOCALE_MAP: Record<string, string> = {
  vi: 'vi_VN',
  en: 'en_US',
  ja: 'ja_JP',
};

const KEYWORDS_MAP: Record<string, string> = {
  vi: 'omaishort, tạo video ngắn AI, story to video, drama short, news short, knowledge video, karaoke captions, edge-tts, ffmpeg ken burns',
  en: 'omaishort, AI short video generator, story to video engine, 1080x1920 vertical video, character bible, karaoke captions, local-first video creator',
  ja: 'omaishort, AIショート動画作成, ストーリー動画生成, 縦型動画, カラオケ字幕, ローカルファースト',
};

export function useSEO({
  titleKey = 'meta.title',
  descriptionKey = 'meta.description',
  path = '',
  lang,
  noindex = false,
}: SEOProps = {}) {
  const { t, i18n } = useTranslation('common');
  const currentLang = lang || i18n.language || 'en';
  const title = t(titleKey);
  const description = t(descriptionKey);
  const siteUrl = SITE_CONFIG.siteUrl;
  const cleanPath = path.replace(/^\/+/, '');
  const canonical = `${siteUrl}/${currentLang}${cleanPath ? `/${cleanPath}` : ''}`;
  const ogImage = `${siteUrl}${SITE_CONFIG.defaultOgImage}`;

  useEffect(() => {
    document.title = title;
    document.documentElement.lang = currentLang;

    setMeta('description', description);
    setMeta('keywords', KEYWORDS_MAP[currentLang] || KEYWORDS_MAP.en);
    setMeta('author', 'omaishort');
    setMeta(
      'robots',
      noindex
        ? 'noindex, nofollow'
        : 'index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1',
    );
    setMeta('og:site_name', 'omaishort');
    setMeta('og:locale', LOCALE_MAP[currentLang] || 'en_US');
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
        setHreflang(lng, `${siteUrl}/${lng}${cleanPath ? `/${cleanPath}` : ''}`);
      }
      setHreflang('x-default', `${siteUrl}/en${cleanPath ? `/${cleanPath}` : ''}`);
    } else {
      removeLink('canonical');
      for (const lng of ['en', 'vi', 'ja', 'x-default']) {
        removeHreflang(lng);
      }
    }

    setJsonLd({
      '@context': 'https://schema.org',
      '@graph': [
        {
          '@type': 'WebSite',
          '@id': `${siteUrl}/#website`,
          url: siteUrl,
          name: 'omaishort',
          description,
          inLanguage: currentLang,
        },
        {
          '@type': 'SoftwareApplication',
          '@id': `${siteUrl}/#software`,
          name: 'omaishort',
          applicationCategory: 'MultimediaApplication',
          operatingSystem: 'Windows, macOS, Linux, Web',
          offers: {
            '@type': 'Offer',
            price: '0',
            priceCurrency: 'USD',
          },
          description,
          url: canonical,
        },
        {
          '@type': 'WebPage',
          '@id': `${canonical}#webpage`,
          url: canonical,
          name: title,
          description,
          isPartOf: { '@id': `${siteUrl}/#website` },
          inLanguage: currentLang,
        },
      ],
    });
  }, [title, description, canonical, currentLang, cleanPath, siteUrl, ogImage, noindex]);
}

function setJsonLd(payload: Record<string, unknown>) {
  let script = document.getElementById('omaishort-jsonld') as HTMLScriptElement | null;
  if (!script) {
    script = document.createElement('script');
    script.id = 'omaishort-jsonld';
    script.type = 'application/ld+json';
    document.head.appendChild(script);
  }
  script.textContent = JSON.stringify(payload);
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
