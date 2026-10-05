import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useScrollReveal } from '../../hooks/useScrollReveal';

export function FAQSection() {
  const { t } = useTranslation('landing');
  const ref = useScrollReveal();
  const items = t('faq.items', { returnObjects: true }) as Array<{ question: string; answer: string }>;
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section id="faq" className="section faq" aria-labelledby="faq-title" ref={ref}>
      <div className="section-inner">
        <p className="kicker">{t('faq.kicker')}</p>
        <h2 id="faq-title" className="section-title">{t('faq.title')}</h2>
        <div className="faq-list">
          {items.map((item, i) => (
            <details
              key={i}
              className="faq-item"
              open={openIndex === i}
              onToggle={(e) => {
                if ((e.target as HTMLDetailsElement).open) {
                  setOpenIndex(i);
                } else if (openIndex === i) {
                  setOpenIndex(null);
                }
              }}
            >
              <summary className="faq-question">
                <span>{item.question}</span>
                <svg className="faq-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="m19 9-7 7-7-7" />
                </svg>
              </summary>
              <div className="faq-answer">
                <p>{item.answer}</p>
              </div>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
