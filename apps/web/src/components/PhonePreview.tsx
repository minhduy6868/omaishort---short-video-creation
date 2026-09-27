type PhonePreviewProps = {
  videoSrc?: string | null;
  poster?: string;
  emptyLabel?: string;
};

export function PhonePreview({ videoSrc, poster, emptyLabel = "1080×1920" }: PhonePreviewProps) {
  return (
    <div className="phone-preview">
      <div className="phone-frame">
        {videoSrc ? (
          <video controls playsInline poster={poster} src={videoSrc} />
        ) : poster ? (
          <img src={poster} alt="" />
        ) : (
          <p className="empty">{emptyLabel}</p>
        )}
      </div>
    </div>
  );
}
