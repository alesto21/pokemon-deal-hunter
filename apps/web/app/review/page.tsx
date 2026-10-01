import { redirect } from "next/navigation";

/** Legacy route: the match-review queue now lives under Listings. */
export default function ReviewRedirect() {
  redirect("/listings?tab=review");
}
