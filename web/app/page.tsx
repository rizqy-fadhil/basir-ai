import { redirect } from "next/navigation";

/**
 * Root page — redirect ke halaman cafe default.
 * MVP single-cafe: cafe_id = 1.
 */
export default function Home() {
  const cafeId = process.env.NEXT_PUBLIC_CAFE_ID ?? "1";
  redirect(`/cafes/${cafeId}`);
}
