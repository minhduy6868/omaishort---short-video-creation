import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { LanguageSwitcher } from './LanguageSwitcher';

export function Header() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const lang = i18n.language || 'en';
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const isStudio = location.pathname.includes('/studio');

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 40);
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  const navItems = [
    { key: 'features', href: '#features' },
    { key: 'howItWorks', href: '#how-it-works' },
    { key: 'demo', href: '#demo' },
    { key: 'faq', href: '#faq' },
  ];

  return (
    <header className={`site-header${scrolled ? ' scrolled' : ''}`} role="banner">
      <div className="header-inner">
        <Link to={`/${lang}`} className="logo" aria-label="omaishort home">
          omaishort
        </Link>

        {!isStudio && (
          <nav
            className={`header-nav${menuOpen ? ' open' : ''}`}
            aria-label="Main navigation"
          >
            {navItems.map((item) => (
              <a
                key={item.key}
                href={item.href}
                className="nav-link"
                onClick={() => setMenuOpen(false)}
              >
                {t(`nav.${item.key}`)}
              </a>
            ))}
          </nav>
        )}

        <div className="header-actions">
          <LanguageSwitcher />
          {isStudio ? (
            <Link to={`/${lang}`} className="header-cta ghost">
              {t('nav.backToHome')}
            </Link>
          ) : (
            <Link to={`/${lang}/studio`} className="header-cta">
              {t('nav.tryStudio')}
            </Link>
          )}
          {!isStudio && (
            <button
              type="button"
              className="menu-toggle"
              aria-label="Toggle menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(!menuOpen)}
            >
              <span className="menu-bar" />
              <span className="menu-bar" />
              <span className="menu-bar" />
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
