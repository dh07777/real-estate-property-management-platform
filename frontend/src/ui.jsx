import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { X, Heart, MapPin, BedDouble, Bath, Ruler } from "lucide-react";
import api, { errMsg } from "./api";

export const inr = (n) => {
  if (n == null || n === "") return "-";
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  return "₹" + Math.round(n).toLocaleString("en-IN");
};
export const fdate = (s) => (s ? new Date(s).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "-");
export const fdt = (s) => (s ? new Date(s).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "-");

const placeholder = (t = "EstateFlow") =>
  "data:image/svg+xml;utf8," + encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='800' height='500'><rect width='100%' height='100%' fill='#1b2a41'/><path d='M250 330V230l150-90 150 90v100z' fill='none' stroke='#b8893b' stroke-width='10'/><text x='400' y='410' fill='#c9ced6' font-family='sans-serif' font-size='28' text-anchor='middle'>${t.replace(/[<>&']/g, "")}</text></svg>`);

export function Img({ src, alt = "", ...rest }) {
  return <img src={src || placeholder(alt)} alt={alt} loading="lazy"
    onError={(e) => { e.currentTarget.onerror = null; e.currentTarget.src = placeholder(alt); }} {...rest} />;
}

const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((msg, type = "ok") => {
    const id = Math.random();
    setItems((x) => [...x, { id, msg, type }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 4000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status">{items.map((i) => <div key={i.id} className={`toast ${i.type}`}>{i.msg}</div>)}</div>
    </ToastCtx.Provider>
  );
}

export function useFetch(fn, deps = []) {
  const [s, setS] = useState({ data: null, meta: null, loading: true, error: null });
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    setS((x) => ({ ...x, loading: true, error: null }));
    fn().then((r) => live && setS({ data: r.data.data, meta: r.data, loading: false, error: null }))
      .catch((e) => live && setS({ data: null, meta: null, loading: false, error: errMsg(e) }));
    return () => { live = false; };
    // eslint-disable-next-line
  }, [...deps, n]);
  return { ...s, reload: () => setN((x) => x + 1) };
}

export const Skeleton = ({ n = 3, h = 90 }) => <div>{Array.from({ length: n }, (_, i) => <div key={i} className="skeleton" style={{ height: h }} />)}</div>;
export const Empty = ({ title, hint, children }) => <div className="empty"><strong>{title}</strong>{hint && <p>{hint}</p>}{children}</div>;
export const ErrorBox = ({ msg, retry }) => <div className="errbox">{msg} {retry && <button className="btn sm" onClick={retry}>Try again</button>}</div>;

export function State({ f, empty, children }) {
  if (f.loading) return <Skeleton />;
  if (f.error) return <ErrorBox msg={f.error} retry={f.reload} />;
  if (Array.isArray(f.data) && !f.data.length) return empty || <Empty title="Nothing here yet" />;
  return children;
}

export function Modal({ title, onClose, children }) {
  useEffect(() => { const k = (e) => e.key === "Escape" && onClose(); window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, [onClose]);
  return (
    <div className="modal-bg" onMouseDown={onClose}>
      <div className="modal" role="dialog" aria-label={title} onMouseDown={(e) => e.stopPropagation()}>
        <div className="row between"><h3>{title}</h3><button className="icon" aria-label="Close" onClick={onClose}><X size={18} /></button></div>
        {children}
      </div>
    </div>
  );
}

export const Chip = ({ v }) => <span className={`chip ${String(v).toLowerCase().replace(/\s/g, "-")}`}>{v}</span>;

export function Pager({ meta, onPage }) {
  if (!meta || meta.pages <= 1) return null;
  return (
    <div className="row center gap">
      <button className="btn sm" disabled={meta.page <= 1} onClick={() => onPage(meta.page - 1)}>Previous</button>
      <span>Page {meta.page} of {meta.pages}</span>
      <button className="btn sm" disabled={meta.page >= meta.pages} onClick={() => onPage(meta.page + 1)}>Next</button>
    </div>
  );
}

export function PropertyCard({ p, onFav }) {
  const price = p.listing_type === "rent" ? `${inr(p.monthly_rent)}/mo` : inr(p.price);
  return (
    <article className="card prop">
      <Link to={`/properties/${p.id}`} className="thumb">
        <Img src={p.cover} alt={p.title} />
        <span className="tag">{p.listing_type === "rent" ? "For rent" : "For sale"}</span>
        {p.featured && <span className="tag feat">Featured</span>}
        {p.status !== "available" && <span className="tag sold">{p.status}</span>}
      </Link>
      <div className="body">
        <div className="row between"><strong className="price">{price}</strong>
          {onFav && <button className={`icon ${p.is_favorite ? "on" : ""}`} aria-label="Save property" onClick={() => onFav(p)}><Heart size={18} fill={p.is_favorite ? "currentColor" : "none"} /></button>}
        </div>
        <Link to={`/properties/${p.id}`} className="title">{p.title}</Link>
        <div className="muted"><MapPin size={14} /> {p.locality}, {p.city}</div>
        <div className="facts"><span><BedDouble size={14} /> {p.bedrooms}</span><span><Bath size={14} /> {p.bathrooms}</span><span><Ruler size={14} /> {p.area_sqft} sqft</span></div>
        {p.is_demo && <small className="muted">Demo listing</small>}
      </div>
    </article>
  );
}

export const Field = ({ label, children }) => <label className="field"><span>{label}</span>{children}</label>;

export function AuthImg({ path, alt = "" }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url;
    api.get(path, { responseType: "blob" }).then((r) => { url = URL.createObjectURL(r.data); setSrc(url); }).catch(() => {});
    return () => url && URL.revokeObjectURL(url);
  }, [path]);
  return src ? <img src={src} alt={alt} style={{ maxWidth: 220, borderRadius: 8 }} /> : null;
}

export const Stars = ({ n }) => <span aria-label={`${n} out of 5`} style={{ color: "var(--brass)" }}>{"★".repeat(Math.round(n || 0))}{"☆".repeat(5 - Math.round(n || 0))}</span>;
