import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useScrollReveal } from '../../hooks/useScrollReveal';

export function CTASection() {
  const { t } = useTranslation('landing');
  const ref = useScrollReveal();

  return (
    <section id="cta" className="section cta-section" aria-labelledby="cta-title" ref={ref}>
      <div className="section-inner">
        <div className="cta-outer-frame">
          <div className="cta-inner">
            <h2 id="cta-title" className="cta-title">{t('cta.title')}</h2>
            <p className="cta-subtitle">{t('cta.subtitle')}</p>

            <div className="cta-actions">
              <Link to="/work" className="btn btn-primary btn-lg">
                <span>{t('cta.button')}</span>
              </Link>
              <Link to="/login" className="btn btn-secondary btn-lg">
                Đăng nhập Studio
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
