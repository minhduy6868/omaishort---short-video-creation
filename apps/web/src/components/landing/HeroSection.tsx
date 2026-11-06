import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

export function HeroSection() {
  const { t } = useTranslation('landing');

  return (
    <section id="hero" className="hero" aria-labelledby="hero-title">
      <div className="hero-inner-wrap">
        <div className="hero-copy-center">
          <p className="hero-kicker-text">{t('hero.kicker')}</p>

          <h1 id="hero-title" className="hero-title">
            {t('hero.title')}
          </h1>

          <p className="hero-subtitle">{t('hero.subtitle')}</p>

          <div className="hero-actions">
            <Link to="/work" className="btn btn-primary btn-lg">
              <span>{t('hero.cta_primary')}</span>
            </Link>
            <a href="#demo" className="btn btn-secondary btn-lg">
              <span>{t('hero.cta_secondary')}</span>
            </a>
          </div>
        </div>

        {/* Clean Product Interface Preview (Linear / Google Workspace style) */}
        <div className="hero-console-outer" aria-label="omaishort Studio Workspace Preview">
          <div className="hero-console-inner">
            <div className="console-header">
              <div className="console-brand-group">
                <div className="console-traffic" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
                <span className="console-title">omaishort Studio — Production Workspace</span>
              </div>
              <span className="console-status-text">Local Engine Ready · 1080×1920 @ 30fps</span>
            </div>

            <div className="console-workspace">
              {/* Left Column: Script & Character Bible */}
              <div className="console-col">
                <div className="console-card">
                  <div className="console-card-head">
                    <span className="console-card-label">Kịch bản đầu vào</span>
                    <span className="console-tag">Drama · 60s</span>
                  </div>
                  <p className="console-prompt-text">
                    Cô lao công khách sạn bị vị khách giàu sỉ nhục giữa sảnh lớn. Đúng lúc đó tổng giám đốc bước ra và cúi đầu gọi cô là mẹ.
                  </p>
                </div>

                <div className="console-card">
                  <div className="console-card-head">
                    <span className="console-card-label">Character Bible</span>
                    <span className="console-tag">Đã khóa khuôn mặt</span>
                  </div>
                  <div className="console-identity-row">
                    <div className="identity-avatar" aria-hidden="true">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="8" r="4" />
                        <path d="M5 20c1.5-4 12.5-4 14 0" />
                      </svg>
                    </div>
                    <div className="identity-info">
                      <strong>Bà Lan · Nhân vật chính</strong>
                      <span>Giữ đồng nhất khuôn mặt và trang phục qua 5 cảnh</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Center Column: 7-Stage Pipeline */}
              <div className="console-col">
                <div className="console-card console-card-full">
                  <div className="console-card-head">
                    <span className="console-card-label">Tiến trình xử lý 7 bước</span>
                    <span className="console-mono-time">Hoàn tất</span>
                  </div>
                  <div className="console-stage-list">
                    {[
                      { name: '1. Analyze', desc: 'Tách nhân vật & cấu trúc 5 nhịp', state: 'Done' },
                      { name: '2. Plan', desc: 'Chia cảnh & chuyển động góc máy', state: 'Done' },
                      { name: '3. References', desc: 'Khóa ảnh gốc cho từng nhân vật', state: 'Done' },
                      { name: '4. Stills', desc: 'Tạo ảnh khung dọc 1080×1920', state: 'Done' },
                      { name: '5. Voiceover', desc: 'Đọc thuyết minh đồng bộ từng từ', state: 'Done' },
                      { name: '6. Captions', desc: 'Tạo phụ đề ASS karaoke', state: 'Done' },
                      { name: '7. Render', desc: 'Xuất file MP4 30fps hoàn chỉnh', state: 'Ready' },
                    ].map((st, idx) => (
                      <div key={st.name} className={`console-stage-item${idx === 6 ? ' active' : ' done'}`}>
                        <div className="stage-text">
                          <strong>{st.name}</strong>
                          <span>{st.desc}</span>
                        </div>
                        <span className="stage-duration">{st.state}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right Column: 9:16 Vertical Output */}
              <div className="console-col">
                <div className="console-card console-card-full console-preview-card">
                  <div className="console-card-head">
                    <span className="console-card-label">Video đầu ra (9:16)</span>
                    <span className="console-tag">MP4 · 30fps</span>
                  </div>

                  <div className="console-viewport">
                    <div className="viewport-hud-top">
                      <span>Cảnh 04 / 05 · Bước ngoặt</span>
                      <span>00:42 / 01:00</span>
                    </div>

                    <div className="viewport-center-badge">
                      <div className="viewport-frame-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="5" y="2" width="14" height="20" rx="2" />
                          <path d="m10 9 5 3-5 3V9Z" />
                        </svg>
                      </div>
                      <span>1080 × 1920 Vertical Master</span>
                    </div>

                    <div className="viewport-caption-bar">
                      <span className="viewport-word">Giữa </span>
                      <span className="viewport-word">sảnh </span>
                      <span className="viewport-word highlighted">khách sạn</span>
                      <span className="viewport-word"> mọi </span>
                      <span className="viewport-word">người </span>
                      <span className="viewport-word">sững sờ.</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
