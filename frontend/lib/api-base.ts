const LOCAL_API_BASE_URL = "http://127.0.0.1:8000";

export function getApiBaseUrl() {
  const configured =
    process.env.API_BASE_URL ||
    process.env.BACKEND_URL ||
    process.env.PUBLIC_BACKEND_URL  ||
    LOCAL_API_BASE_URL;

  return configured.replace(/\/+$/, "");
}

export function apiUrl(path: string) {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${cleanPath}`;
}
