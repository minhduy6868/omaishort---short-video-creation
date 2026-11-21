import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useScrollReveal } from '../../hooks/useScrollReveal';

const DESKTOP_DOWNLOAD_URL =
  (import.meta.env.VITE_DESKTOP_DOWNLOAD_URL as string | undefined) ||
  'https://github.com/minhduy6868/omaishort---short-video-creation/releases/latest/download/omaishort-win-x64.zip';

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
              <a href={DESKTOP_DOWNLOAD_URL} className="btn btn-primary btn-lg" rel="noopener noreferrer">
                <span>Tải omaishort cho Windows (.zip)</span>
              </a>
              <Link to="/work" className="btn btn-secondary btn-lg">
                <span>{t('cta.button')}</span>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
