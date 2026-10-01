import { redirect } from "next/navigation";

/** Collector health moved to /system (worker, lock, runs) and /alerts (alert history). */
export default function HealthPage() {
  redirect("/system");
}
