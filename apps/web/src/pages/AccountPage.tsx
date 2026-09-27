import { useEffect, useState } from "react";
import { readProviders, type ProviderStatus } from "../api";
import { useSession } from "../session";

function chips(status: ProviderStatus): { id: string; on: boolean; label: string }[] {
  const image = status.image ?? {};
  const motion = status.drama_motion ?? "kenburns";
  return [
    { id: "chatgpt", on: Boolean(status.chatgpt_web_authed), label: status.chatgpt_web_authed ? "ChatGPT VO" : "ChatGPT off" },
    { id: "motion", on: motion !== "kenburns", label: `motion ${motion}` },
    { id: "edge", on: Boolean(status.tts?.edge), label: "edge-tts" },
    { id: "image", on: Object.values(image).some(Boolean), label: "image" },
  ];
}

export function AccountPage() {
  const { user } = useSession();
  const [providers, setProviders] = useState<ProviderStatus | null>(null);

  useEffect(() => {
    void readProviders().then(setProviders);
  }, []);

  return (
    <section>
      <p className="kicker">Tài khoản</p>
      <h1>{user?.display_name || user?.email}</h1>
      <p className="lede">
        {user?.email} · {user?.role}
      </p>
      <p className="meta">Đăng nhập ChatGPT nằm ở trang Kiến thức. Drama và News không dùng phiên đó.</p>
      {providers ? (
        <ul className="chips" aria-label="Trạng thái máy">
          {chips(providers).map((chip) => (
            <li key={chip.id} className={chip.on ? "on" : "off"}>
              {chip.label}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
