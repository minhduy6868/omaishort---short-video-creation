import type { ScenePreview } from "../types";

export type SceneWithSrc = ScenePreview & {
  src: string | null;
};

type SceneStripProps = {
  scenes: SceneWithSrc[];
};

export function SceneStrip({ scenes }: SceneStripProps) {
  if (!scenes.length) return null;

  return (
    <div className="scene-strip">
      {scenes.map((scene) => (
        <article className="scene-card" key={`${scene.index}-${scene.still_id}`}>
          {scene.src ? <img src={scene.src} alt="" /> : <span className="ph" />}
          <div>
            <p className="scene-title">
              Scene {scene.index + 1} · {scene.duration_sec}s
            </p>
            <p className="scene-meta">
              {scene.emotion || "neutral"} · {scene.location || "no location"}
            </p>
            <p className="scene-copy">{scene.dialogue_or_vo}</p>
            {scene.shots.length ? (
              <p className="scene-meta">{scene.shots.map((shot) => `${shot.camera}/${shot.motion}`).join(" → ")}</p>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}
