import { useTranslation } from 'react-i18next';
import { useScrollReveal } from '../../hooks/useScrollReveal';

export function UseCasesSection() {
  const { t } = useTranslation('landing');
  const ref = useScrollReveal();
  const items = t('useCases.items', { returnObjects: true }) as Array<{ title: string; description: string; example: string }>;

  return (
    <section className="section use-cases" aria-labelledby="cases-title" ref={ref}>
      <div className="section-inner">
        <div className="section-header-block">
          <p className="kicker">{t('useCases.kicker')}</p>
          <h2 id="cases-title" className="section-title">{t('useCases.title')}</h2>
        </div>

        <div className="use-cases-grid">
          {items.map((item, i) => (
            <article key={i} className="use-case-card">
              <div className="use-case-top">
                <h3>{item.title}</h3>
                <p>{item.description}</p>
              </div>
              <div className="use-case-example-box">
                <blockquote className="use-case-example">{item.example}</blockquote>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
