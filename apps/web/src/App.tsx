import { useEffect } from "react";
import { Shell } from "./Shell";
import { useNav } from "./nav";
import { AccountPage } from "./pages/AccountPage";
import { ComposePage } from "./pages/ComposePage";
import { Gate } from "./pages/Gate";
import { JobPage } from "./pages/JobPage";
import { WorkPage } from "./pages/WorkPage";
import { useSession } from "./session";
import "./App.css";

function Redirect({ to }: { to: string }) {
  const { go } = useNav();
  useEffect(() => {
    go(to);
  }, [go, to]);
  return null;
}

export default function App() {
  const { route } = useNav();
  const { user, ready } = useSession();

  if (!ready) return <p className="boot">Đang mở studio…</p>;

  const gate = route.name === "login" || route.name === "register";
  if (!user && !gate) return <Redirect to="/login" />;
  if (user && gate) return <Redirect to="/work" />;
  if (!user && route.name === "login") return <Gate mode="login" />;
  if (!user && route.name === "register") return <Gate mode="register" />;

  let page = <WorkPage />;
  if (route.name === "drama" || route.name === "news" || route.name === "knowledge") {
    page = <ComposePage key={route.name} kind={route.name} />;
  }
  if (route.name === "account") page = <AccountPage />;
  if (route.name === "watch") page = <JobPage key={route.id} id={route.id} />;

  return <Shell>{page}</Shell>;
}
