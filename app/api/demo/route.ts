/* The demo sign-in for the login page. Only answers when AERA_DEMO_EMAIL and
 * AERA_DEMO_PASSWORD are set; point them at a viewer account, which approves
 * nothing and changes no settings, since anyone who opens /login sees them. */
export async function GET() {
  const email = process.env.AERA_DEMO_EMAIL;
  const password = process.env.AERA_DEMO_PASSWORD;
  if (!email || !password) return Response.json({ enabled: false });
  return Response.json({ enabled: true, email, password });
}
