import { useTranslation } from 'react-i18next';
import { useScrollReveal } from '../../hooks/useScrollReveal';

const KINDS = ['drama', 'news', 'knowledge'] as const;

const KIND_ICONS: Record<string, string> = {
  drama: 'M15.91 11.672a.375.375 0 0 1 0 .656l-6.54 3.78a.375.375 0 0 1-.563-.328V8.22a.375.375 0 0 1 .563-.327l6.54 3.78Z',
  news: 'M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 0 1-2.25 2.25M16.5 7.5V18a2.25 2.25 0 0 0 2.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 0 0 2.25 2.25h13.5',
  knowledge: 'M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342',
};

export function FeaturesSection() {
  const { t } = useTranslation('landing');
  const ref = useScrollReveal();

  return (
    <section id="features" className="section features" aria-labelledby="features-title" ref={ref}>
      <div className="section-inner">
        <p className="kicker">{t('features.kicker')}</p>
        <h2 id="features-title" className="section-title">{t('features.title')}</h2>
        <div className="features-grid">
          {KINDS.map((kind) => (
            <article key={kind} className="feature-card">
              <div className="feature-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d={KIND_ICONS[kind]} />
                </svg>
              </div>
              <h3>{t(`features.${kind}.title`)}</h3>
              <p>{t(`features.${kind}.description`)}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
