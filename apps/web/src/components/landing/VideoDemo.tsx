import { useState, useRef, useEffect } from 'react';

export interface VideoDemoProps {
  src: string;
  poster?: string;
  title: string;
  description?: string;
  aspectRatio?: '9/16' | '16/9';
  className?: string;
}

export function VideoDemo({
  src,
  poster,
  title,
  description,
  aspectRatio = '9/16',
  className = '',
}: VideoDemoProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(true);
  const [isInView, setIsInView] = useState(false);
  const [progress, setProgress] = useState(0);

  // Lazy loading via IntersectionObserver
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsInView(true);
            observer.disconnect();
          }
        });
      },
      { rootMargin: '100px' }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const isExternalUrl = (url: string) => {
    return url.startsWith('http://') || url.startsWith('https://');
  };

  const handleTogglePlay = () => {
    const video = videoRef.current;
    if (!video) return;

    if (isPlaying) {
      video.pause();
    } else {
      video.play().catch((err) => console.warn('Video play prevented:', err));
    }
  };

  const handleToggleMute = (e: React.MouseEvent) => {
    e.stopPropagation();
    const video = videoRef.current;
    if (!video) return;
    video.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (!video || !video.duration) return;
    setProgress((video.currentTime / video.duration) * 100);
  };

  const isExternal = isExternalUrl(src);

  return (
    <article className={`video-demo-card ${className}`} ref={containerRef}>
      <div
        className="video-demo-player-wrapper"
        style={{ aspectRatio: aspectRatio === '9/16' ? '9 / 16' : '16 / 9' }}
      >
        {isExternal && src.includes('youtube.com') ? (
          <iframe
            src={src}
            title={title}
            loading="lazy"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="video-demo-iframe"
          />
        ) : (
          <>
            <video
              ref={videoRef}
              playsInline
              muted={isMuted}
              preload={isInView ? 'metadata' : 'none'}
              poster={poster}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onEnded={() => setIsPlaying(false)}
              onTimeUpdate={handleTimeUpdate}
              onClick={handleTogglePlay}
              aria-label={title}
              className="video-demo-element"
            >
              {isInView && <source src={src} type="video/mp4" />}
            </video>

            {/* Custom Overlay Controls */}
            <div className="video-demo-overlay" onClick={handleTogglePlay}>
              {!isPlaying && (
                <button
                  type="button"
                  className="video-demo-play-btn"
                  aria-label={`Play ${title}`}
                >
                  <svg viewBox="0 0 24 24" fill="currentColor" width="36" height="36">
                    <path d="M8 5.14v14l11-7-11-7Z" />
                  </svg>
                </button>
              )}

              {isPlaying && (
                <div className="video-demo-bottom-bar" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className="video-demo-mute-btn"
                    onClick={handleToggleMute}
                    aria-label={isMuted ? 'Unmute' : 'Mute'}
                  >
                    {isMuted ? (
                      <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                        <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                        <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
                      </svg>
                    )}
                  </button>
                  <div className="video-demo-progress-track">
                    <div
                      className="video-demo-progress-fill"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="video-demo-info">
        <h3 className="video-demo-title">{title}</h3>
        {description && <p className="video-demo-desc">{description}</p>}
      </div>
    </article>
  );
}
