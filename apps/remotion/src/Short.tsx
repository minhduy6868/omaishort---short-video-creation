import React from "react";

type Element = {
  id: string;
  src: string;
  from_sec: number;
  duration_sec: number;
  animation: string;
};

type Timeline = {
  shortTitle: string;
  width: number;
  height: number;
  fps: number;
  elements: Element[];
  text: Array<{ text: string; from_sec: number; duration_sec: number }>;
  audio: Array<{ src: string; duration_sec: number }>;
};

/** Placeholder composition. Wire Remotion Player in a later phase. */
export const Short: React.FC<{ timeline: Timeline }> = ({ timeline }) => {
  return (
    <div
      style={{
        width: timeline.width,
        height: timeline.height,
        background: "#111",
        color: "white",
        fontFamily: "sans-serif",
        padding: 48,
      }}
    >
      <h1>{timeline.shortTitle}</h1>
      <p>{timeline.elements.length} stills · {timeline.audio[0]?.duration_sec ?? 0}s</p>
    </div>
  );
};
