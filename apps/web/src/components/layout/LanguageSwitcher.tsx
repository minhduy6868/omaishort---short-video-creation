import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation } from 'react-router-dom';
import { SUPPORTED_LANGS, LANG_LABELS, type SupportedLang } from '../../i18n';

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const current = (SUPPORTED_LANGS.includes(i18n.language as SupportedLang)
    ? i18n.language
    : 'en') as SupportedLang;

  function switchLang(lang: SupportedLang) {
    void i18n.changeLanguage(lang);
    const rest = location.pathname.replace(/^\/(en|vi|ja)/, '');
    navigate(`/${lang}${rest || ''}`);
  }

  return (
    <div className="lang-switcher">
      <button
        type="button"
        className="lang-trigger"
        aria-label="Change language"
        aria-haspopup="listbox"
      >
        {LANG_LABELS[current]}
      </button>
      <ul className="lang-menu" role="listbox" aria-label="Language">
        {SUPPORTED_LANGS.map((lang) => (
          <li key={lang} role="option" aria-selected={lang === current}>
            <button
              type="button"
              className={lang === current ? 'active' : ''}
              onClick={() => switchLang(lang)}
            >
              {LANG_LABELS[lang]}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
