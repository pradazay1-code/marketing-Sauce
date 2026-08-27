import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { checkPassword, mintToken, isAuthed, SESSION_COOKIE } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  if (await isAuthed()) redirect("/");
  const { error } = await searchParams;

  async function login(formData: FormData) {
    "use server";
    const password = String(formData.get("password") ?? "");
    if (!checkPassword(password)) redirect("/login?error=1");

    const token = mintToken();
    const jar = await cookies();
    jar.set(SESSION_COOKIE, token.value, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: token.maxAge,
      path: "/",
    });
    redirect("/");
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="agent">VERA</div>
        <div className="rule" />
        <div className="org">One Vision Marketing</div>

        {error && <div className="err">Incorrect password.</div>}

        <form action={login}>
          <input
            type="password"
            name="password"
            placeholder="Password"
            autoFocus
            required
            autoComplete="current-password"
          />
          <button className="btn" style={{ width: "100%", marginTop: 12 }}>
            Sign in
          </button>
        </form>
      </div>
    </div>
  );
}
