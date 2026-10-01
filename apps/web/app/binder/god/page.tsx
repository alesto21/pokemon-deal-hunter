"use client";

import { Crown } from "lucide-react";
import BinderView from "@/components/collection/BinderView";

export default function GodBinderPage() {
  return (
    <BinderView
      binderType="premium"
      title="GOD Binder"
      subtitle="Premium top-loader binder — chase cards, iconic Pokémon and long-term holds"
      icon={Crown}
    />
  );
}
