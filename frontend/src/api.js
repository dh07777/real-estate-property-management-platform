import axios from "axios";

const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("ef_token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401 && localStorage.getItem("ef_token") && !e.config.url.includes("/auth/login")) {
      localStorage.removeItem("ef_token");
      window.location.href = "/login";
    }
    return Promise.reject(e);
  }
);

export const errMsg = (e) => {
  const d = e.response?.data;
  if (d?.errors) return Object.entries(d.errors).map(([k, v]) => `${k}: ${v}`).join(", ");
  return d?.message || (e.request ? "Cannot reach the server. Is the backend running?" : e.message);
};

export async function download(path, filename) {
  const r = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(r.data);
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

export default api;
