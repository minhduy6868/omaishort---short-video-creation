import { useTranslation } from 'react-i18next';
import { useScrollReveal } from '../../hooks/useScrollReveal';
import { VideoDemo } from './VideoDemo';

export function DemoSection() {
  const { t } = useTranslation('landing');
  const ref = useScrollReveal();
  const items = t('demo.items', { returnObjects: true }) as Array<{ title: string; description: string }>;

  const demos = [
    {
      src: '/demo/knowledge-history.mp4',
      poster: '/demo/knowledge-history.jpg',
    },
    {
      src: '/demo/knowledge-skills.mp4',
      poster: '/demo/knowledge-skills.jpg',
    },
  ];

  return (
    <section id="demo" className="section demo" aria-labelledby="demo-title" ref={ref}>
      <div className="section-inner">
        <p className="kicker">{t('demo.kicker')}</p>
        <h2 id="demo-title" className="section-title">{t('demo.title')}</h2>
        <p className="section-subtitle">{t('demo.subtitle')}</p>
        <div className="demo-grid">
          {items.map((item, i) => {
            const demoAsset = demos[i] || demos[0];
            return (
              <VideoDemo
                key={i}
                src={demoAsset.src}
                poster={demoAsset.poster}
                title={item.title}
                description={item.description}
                aspectRatio="9/16"
              />
            );
          })}
        </div>
      </div>
    </section>
  );
}
