import { FormEvent, useState } from "react";
import { login, register } from "../api";
import { useNav } from "../nav";
import { useSession } from "../session";

export function Gate({ mode }: { mode: "login" | "register" }) {
  const { go } = useNav();
  const { setUser } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const registering = mode === "register";

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    try {
      const me = registering
        ? await register(email, password, name.trim() || undefined)
        : await login(email, password);
      setUser(me);
      go("/work");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Auth failed");
    }
  }

  return (
    <main className="gate">
      <p className="kicker">omaishort</p>
      <h1>{registering ? "Đăng ký" : "Đăng nhập"}</h1>
      <p className="lede">Tài khoản giữ job và file của bạn. Video vẫn render trên máy này.</p>
      <form className="panel narrow" onSubmit={(event) => void onSubmit(event)}>
        {registering ? (
          <label>
            Tên
            <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
          </label>
        ) : null}
        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Mật khẩu
          <input
            type="password"
            autoComplete={registering ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        </label>
        {message ? <p className="err">{message}</p> : null}
        <div className="actions">
          <button type="submit">{registering ? "Tạo tài khoản" : "Vào studio"}</button>
          <button
            type="button"
            className="ghost"
            onClick={() => go(registering ? "/login" : "/register")}
          >
            {registering ? "Đã có tài khoản? Đăng nhập" : "Chưa có tài khoản? Đăng ký"}
          </button>
        </div>
      </form>
    </main>
  );
}
