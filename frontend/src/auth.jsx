import { createContext, useContext, useEffect, useState } from "react";
import api from "./api";

export const MANAGERS = ["super_admin", "agency_owner", "property_manager"];
export const ADMINS = ["super_admin", "agency_owner"];
export const STAFF = [...MANAGERS, "agent"];
export const ROLE_LABEL = { super_admin: "Super Admin", agency_owner: "Agency Owner", property_manager: "Property Manager",
  agent: "Agent", owner: "Owner", tenant: "Tenant", buyer: "Buyer" };

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!localStorage.getItem("ef_token"));

  useEffect(() => {
    if (!localStorage.getItem("ef_token")) return;
    api.get("/auth/me").then((r) => setUser(r.data.data)).catch(() => localStorage.removeItem("ef_token")).finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    localStorage.setItem("ef_token", r.data.data.token);
    setUser(r.data.data.user);
    return r.data.data.user;
  };
  const logout = async () => {
    try { await api.post("/auth/logout"); } catch { /* token may already be invalid */ }
    localStorage.removeItem("ef_token");
    setUser(null);
  };
  return <Ctx.Provider value={{ user, setUser, loading, login, logout }}>{children}</Ctx.Provider>;
}
