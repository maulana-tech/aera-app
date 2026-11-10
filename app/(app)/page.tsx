import { redirect } from "next/navigation";

/* The front door is the dashboard, which sends a business that has not been
 * described yet on to onboarding. */
export default function Home() {
  redirect("/dashboard");
}
