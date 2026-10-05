import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

export function HeroSection() {
  const { t, i18n } = useTranslation('landing');
  const lang = i18n.language || 'en';

  return (
    <section id="hero" className="hero" aria-labelledby="hero-title">
      <div className="hero-inner">
        <p className="kicker">{t('hero.kicker')}</p>
        <h1 id="hero-title" className="hero-title">{t('hero.title')}</h1>
        <p className="hero-subtitle">{t('hero.subtitle')}</p>
        <div className="hero-actions">
          <Link to={`/${lang}/studio`} className="btn btn-primary">
            {t('hero.cta_primary')}
          </Link>
          <a href="#how-it-works" className="btn btn-secondary">
            {t('hero.cta_secondary')}
          </a>
        </div>
      </div>
      <div className="hero-glow" aria-hidden="true" />
    </section>
  );
}
