import React from "react";
import { Short } from "./Short";
import sample from "./sample-timeline.json";

export const Root: React.FC = () => {
  return <Short timeline={sample} />;
};
