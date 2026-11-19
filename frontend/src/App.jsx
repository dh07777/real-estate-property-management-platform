import { Routes, Route, Navigate, NavLink, Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { Bell, Moon, Sun, LogOut } from "lucide-react";
import api from "./api";
import { useAuth, MANAGERS, ADMINS, STAFF } from "./auth";
import { Skeleton } from "./ui";
import { Login, Register, Forgot, Profile } from "./pages/Auth";
import { Listings, PropertyDetail } from "./pages/Listings";
import Dashboard from "./pages/Dashboard";
import { ManageList, PropertyForm } from "./pages/Manage";
import { Inquiries, Appointments, Rentals, Maintenance, Notifications, Favorites } from "./pages/Workflows";
import { Users, Reports, AuditLogs } from "./pages/Admin";
import { Offers, Deals } from "./pages/Sales";
import { Documents } from "./pages/Documents";
import Finance from "./pages/Finance";
import { Vendors, Moderation, Settings } from "./pages/Extra";

function navFor(role) {
  const n = [{ to: "/dashboard", label: "Dashboard" }, { to: "/", label: "Browse", end: true }];
  if (["owner", ...STAFF].includes(role)) n.push({ to: "/manage", label: "Properties" });
  if (role === "buyer") n.push({ to: "/favorites", label: "Saved" });
  n.push({ to: "/inquiries", label: STAFF.includes(role) ? "Leads" : "Inquiries" }, { to: "/appointments", label: "Visits" });
  if (["tenant", "owner", ...MANAGERS].includes(role)) n.push({ to: "/rentals", label: "Rentals" }, { to: "/maintenance", label: "Maintenance" });
  if (["buyer", "owner", ...STAFF].includes(role)) n.push({ to: "/offers", label: "Offers" }, { to: "/deals", label: "Deals" });
  n.push({ to: "/documents", label: "Documents" });
  if ([...MANAGERS, "owner"].includes(role)) n.push({ to: "/finance", label: "Finance" });
  if (MANAGERS.includes(role)) n.push({ to: "/reports", label: "Reports" }, { to: "/vendors", label: "Vendors" }, { to: "/moderation", label: "Reviews" });
  if (ADMINS.includes(role)) n.push({ to: "/users", label: "Users" }, { to: "/settings", label: "Settings" }, { to: "/audit", label: "Audit log" });
  return n;
}

function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [dark, setDark] = useState(localStorage.getItem("ef_theme") === "dark");
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("ef_theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    if (!user) return;
    const load = () => api.get("/notifications?per_page=1").then((r) => setUnread(r.data.unread)).catch(() => {});
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [user]);
  return (
    <>
      <header className="top"><div className="bar">
        <Link to="/" className="brand">Estate<b>Flow</b></Link>
        <nav className="main" aria-label="Main">{(user ? navFor(user.role) : [{ to: "/", label: "Browse", end: true }]).map((l) => <NavLink key={l.to} to={l.to} end={l.end}>{l.label}</NavLink>)}</nav>
        <button className="icon" aria-label="Toggle theme" onClick={() => setDark(!dark)}>{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
        {user ? (<>
          <button className="icon" aria-label="Notifications" onClick={() => nav("/notifications")}><Bell size={18} />{unread > 0 && <span className="badge">{unread}</span>}</button>
          <Link to="/profile" className="muted">{user.name}</Link>
          <button className="icon" aria-label="Sign out" onClick={async () => { await logout(); nav("/login"); }}><LogOut size={18} /></button>
        </>) : <><Link className="btn sm" to="/login">Sign in</Link><Link className="btn sm primary" to="/register">Register</Link></>}
      </div></header>
      <main className="container">{children}</main>
    </>
  );
}

function Protected({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) return <Skeleton />;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/dashboard" replace />;
  return children;
}

export default function App() {
  const P = (el, roles) => <Protected roles={roles}>{el}</Protected>;
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Listings />} />
        <Route path="/properties/:id" element={<PropertyDetail />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot" element={<Forgot />} />
        <Route path="/dashboard" element={P(<Dashboard />)} />
        <Route path="/profile" element={P(<Profile />)} />
        <Route path="/manage" element={P(<ManageList />, ["owner", ...STAFF])} />
        <Route path="/manage/new" element={P(<PropertyForm />, ["owner", ...STAFF])} />
        <Route path="/manage/:id" element={P(<PropertyForm />, ["owner", ...STAFF])} />
        <Route path="/favorites" element={P(<Favorites />)} />
        <Route path="/inquiries" element={P(<Inquiries />)} />
        <Route path="/appointments" element={P(<Appointments />)} />
        <Route path="/rentals" element={P(<Rentals />, ["tenant", "owner", ...MANAGERS])} />
        <Route path="/maintenance" element={P(<Maintenance />, ["tenant", "owner", ...MANAGERS])} />
        <Route path="/notifications" element={P(<Notifications />)} />
        <Route path="/reports" element={P(<Reports />, MANAGERS)} />
        <Route path="/users" element={P(<Users />, ADMINS)} />
        <Route path="/offers" element={P(<Offers />, ["buyer", "owner", ...STAFF])} />
        <Route path="/deals" element={P(<Deals />, ["buyer", "owner", ...STAFF])} />
        <Route path="/documents" element={P(<Documents />)} />
        <Route path="/finance" element={P(<Finance />, [...MANAGERS, "owner"])} />
        <Route path="/vendors" element={P(<Vendors />, MANAGERS)} />
        <Route path="/moderation" element={P(<Moderation />, MANAGERS)} />
        <Route path="/settings" element={P(<Settings />, ADMINS)} />
        <Route path="/audit" element={P(<AuditLogs />, ADMINS)} />
        <Route path="*" element={<div className="empty"><strong>Page not found</strong></div>} />
      </Routes>
    </Layout>
  );
}
