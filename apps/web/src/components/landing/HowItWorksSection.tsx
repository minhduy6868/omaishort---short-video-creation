import { useTranslation } from 'react-i18next';
import { useScrollReveal } from '../../hooks/useScrollReveal';

export function HowItWorksSection() {
  const { t } = useTranslation('landing');
  const ref = useScrollReveal();
  const steps = t('howItWorks.steps', { returnObjects: true }) as Array<{ title: string; description: string }>;

  return (
    <section id="how-it-works" className="section how-it-works" aria-labelledby="how-title" ref={ref}>
      <div className="section-inner">
        <p className="kicker">{t('howItWorks.kicker')}</p>
        <h2 id="how-title" className="section-title">{t('howItWorks.title')}</h2>
        <div className="steps-grid">
          {steps.map((step, i) => (
            <article key={i} className="step-card">
              <div className="step-number" aria-hidden="true">{String(i + 1).padStart(2, '0')}</div>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
