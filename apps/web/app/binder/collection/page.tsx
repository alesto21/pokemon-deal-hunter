"use client";

import { BookOpen } from "lucide-react";
import BinderView from "@/components/collection/BinderView";

export default function CollectionBinderPage() {
  return (
    <BinderView
      binderType="regular"
      title="Collection"
      subtitle="Regular sleeved binder — IRs, URs, promos and the rest of the collection"
      icon={BookOpen}
    />
  );
}
