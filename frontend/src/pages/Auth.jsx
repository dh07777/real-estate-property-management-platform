import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth, ROLE_LABEL } from "../auth";
import { useToast, Field } from "../ui";

const DEMO = [["admin", "Super Admin"], ["agency", "Agency Owner"], ["manager", "Manager"], ["agent", "Agent"], ["owner", "Owner"], ["tenant", "Tenant"], ["buyer", "Buyer"]];

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const [f, setF] = useState({ email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { await login(f.email, f.password); nav("/dashboard"); } catch (er) { toast(errMsg(er), "err"); } finally { setBusy(false); }
  };
  return (
    <div className="card authbox">
      <h2>Sign in</h2>
      <form className="form" onSubmit={submit}>
        <Field label="Email"><input type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Password"><input type="password" required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
        <button className="btn primary" disabled={busy}>{busy ? "Signing in..." : "Sign in"}</button>
      </form>
      <p className="muted"><Link to="/forgot">Forgot password?</Link> · <Link to="/register">Create account</Link></p>
      <div className="demo"><p className="muted">Demo accounts (password Demo@1234). Fill the form:</p>
        {DEMO.map(([k, l]) => <button key={k} type="button" className="btn sm" onClick={() => setF({ email: `${k}@estateflow.demo`, password: "Demo@1234" })}>{l}</button>)}</div>
    </div>
  );
}

export function Register() {
  const nav = useNavigate();
  const toast = useToast();
  const [f, setF] = useState({ name: "", email: "", phone: "", password: "", role: "buyer" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    try { await api.post("/auth/register", f); toast("Account created. Please sign in."); nav("/login"); } catch (er) { toast(errMsg(er), "err"); }
  };
  return (
    <div className="card authbox">
      <h2>Create account</h2>
      <form className="form" onSubmit={submit}>
        <Field label="Full name"><input required value={f.name} onChange={set("name")} /></Field>
        <Field label="Email"><input type="email" required value={f.email} onChange={set("email")} /></Field>
        <Field label="Phone"><input value={f.phone} onChange={set("phone")} /></Field>
        <Field label="I am a"><select value={f.role} onChange={set("role")}>{["buyer", "tenant", "owner"].map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select></Field>
        <Field label="Password (8+ characters, letters and numbers)"><input type="password" required minLength={8} value={f.password} onChange={set("password")} /></Field>
        <button className="btn primary">Create account</button>
      </form>
    </div>
  );
}

export function Forgot() {
  const toast = useToast();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [pw, setPw] = useState("");
  const request = async (e) => {
    e.preventDefault();
    try {
      const r = await api.post("/auth/forgot-password", { email });
      toast(r.data.data.message);
      if (r.data.data.dev_reset_token) setToken(r.data.data.dev_reset_token);
    } catch (er) { toast(errMsg(er), "err"); }
  };
  const reset = async (e) => {
    e.preventDefault();
    try { await api.post("/auth/reset-password", { token, new_password: pw }); toast("Password reset"); nav("/login"); } catch (er) { toast(errMsg(er), "err"); }
  };
  return (
    <div className="card authbox">
      <h2>Reset password</h2>
      <form className="form" onSubmit={request}>
        <Field label="Account email"><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <button className="btn">Get reset token</button>
      </form>
      <p className="muted">No email server is configured. In development the token appears here automatically; in production connect an email service.</p>
      <form className="form" onSubmit={reset}>
        <Field label="Reset token"><input required value={token} onChange={(e) => setToken(e.target.value)} /></Field>
        <Field label="New password"><input type="password" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
        <button className="btn primary">Set new password</button>
      </form>
    </div>
  );
}

export function Profile() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [f, setF] = useState({ name: user.name, phone: user.phone || "" });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const save = async (e) => {
    e.preventDefault();
    try { const r = await api.put("/auth/profile", f); setUser(r.data.data); toast("Profile saved"); } catch (er) { toast(errMsg(er), "err"); }
  };
  const change = async (e) => {
    e.preventDefault();
    try { await api.post("/auth/change-password", pw); setPw({ current_password: "", new_password: "" }); toast("Password changed"); } catch (er) { toast(errMsg(er), "err"); }
  };
  return (
    <div className="grid g2">
      <form className="card form" onSubmit={save}>
        <h3>Profile</h3><p className="muted">{user.email} · {ROLE_LABEL[user.role]}</p>
        <Field label="Name"><input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Phone"><input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
        <button className="btn primary">Save profile</button>
      </form>
      <form className="card form" onSubmit={change}>
        <h3>Change password</h3>
        <Field label="Current password"><input type="password" required value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
        <Field label="New password"><input type="password" required minLength={8} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
        <button className="btn primary">Update password</button>
      </form>
    </div>
  );
}
