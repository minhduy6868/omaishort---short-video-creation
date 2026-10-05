import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSEO } from '../hooks/useSEO';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import App from '../App';

export function StudioPage() {
  const { lang } = useParams<{ lang: string }>();
  const { i18n } = useTranslation();
  const navigate = useNavigate();

  useSEO({ path: 'studio' });

  useEffect(() => {
    if (lang && lang !== i18n.language) {
      void i18n.changeLanguage(lang);
    }
  }, [lang, i18n]);

  useEffect(() => {
    if (!lang || !['en', 'vi', 'ja'].includes(lang)) {
      navigate(`/${i18n.language || 'en'}/studio`, { replace: true });
    }
  }, [lang, i18n.language, navigate]);

  return (
    <>
      <Header />
      <App />
      <Footer />
    </>
  );
}
