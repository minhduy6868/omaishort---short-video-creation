import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useSEO } from "../hooks/useSEO";
import { Header } from "../components/layout/Header";
import { Footer } from "../components/layout/Footer";
import { HeroSection } from "../components/landing/HeroSection";
import { FeaturesSection } from "../components/landing/FeaturesSection";
import { CapabilitiesSection } from "../components/landing/CapabilitiesSection";
import { HowItWorksSection } from "../components/landing/HowItWorksSection";
import { DemoSection } from "../components/landing/DemoSection";
import { UseCasesSection } from "../components/landing/UseCasesSection";
import { FAQSection } from "../components/landing/FAQSection";
import { CTASection } from "../components/landing/CTASection";
import "../styles/landing.css";

export function LandingPage() {
  const { lang } = useParams<{ lang: string }>();
  const { t, i18n } = useTranslation();

  useSEO();

  useEffect(() => {
    if (lang && lang !== i18n.language) {
      void i18n.changeLanguage(lang);
    }
  }, [lang, i18n]);

  return (
    <>
      <a className="skip-link" href="#main">
        {t("nav.skip")}
      </a>
      <Header />
      <main id="main" role="main">
        <HeroSection />
        <FeaturesSection />
        <CapabilitiesSection />
        <HowItWorksSection />
        <DemoSection />
        <UseCasesSection />
        <FAQSection />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
