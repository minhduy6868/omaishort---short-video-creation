import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useScrollReveal } from '../../hooks/useScrollReveal';

export function CTASection() {
  const { t, i18n } = useTranslation('landing');
  const ref = useScrollReveal();
  const lang = i18n.language || 'en';

  return (
    <section id="cta" className="section cta-section" aria-labelledby="cta-title" ref={ref}>
      <div className="section-inner cta-inner">
        <h2 id="cta-title" className="cta-title">{t('cta.title')}</h2>
        <p className="cta-subtitle">{t('cta.subtitle')}</p>
        <Link to={`/${lang}/studio`} className="btn btn-primary btn-lg">
          {t('cta.button')}
        </Link>
      </div>
    </section>
  );
}
