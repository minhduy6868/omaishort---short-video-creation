import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { LanguageSwitcher } from './LanguageSwitcher';

export function Footer() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language || 'en';
  const year = new Date().getFullYear();

  return (
    <footer className="site-footer" role="contentinfo">
      <div className="footer-inner">
        <div className="footer-brand">
          <Link to={`/${lang}`} className="footer-logo">
            omaishort
          </Link>
          <p className="footer-tagline">{t('footer.tagline')}</p>
        </div>

        <div className="footer-links">
          <div className="footer-col">
            <h4>{t('footer.product')}</h4>
            <ul>
              <li><Link to={`/${lang}/studio`}>{t('footer.studio')}</Link></li>
              <li><a href="#features">{t('nav.features')}</a></li>
              <li><a href="#demo">{t('nav.demo')}</a></li>
            </ul>
          </div>
          <div className="footer-col">
            <h4>{t('footer.resources')}</h4>
            <ul>
              <li><a href="https://github.com/minhduy6868/omaishort---short-video-creation" target="_blank" rel="noopener noreferrer">{t('footer.github')}</a></li>
              <li><a href="https://github.com/minhduy6868/omaishort---short-video-creation/tree/main/docs" target="_blank" rel="noopener noreferrer">{t('footer.documentation')}</a></li>
            </ul>
          </div>
        </div>

        <div className="footer-bottom">
          <p>{t('footer.copyright', { year })}</p>
          <LanguageSwitcher />
        </div>
      </div>
    </footer>
  );
}
