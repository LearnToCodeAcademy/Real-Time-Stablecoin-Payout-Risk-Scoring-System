const defaultBase = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiClient {
  baseUrl: string;
  apiKey: string;

  constructor() {
    this.baseUrl = localStorage.getItem("risk-api-base") || defaultBase;
    this.apiKey = localStorage.getItem("risk-api-key") || "";
  }

  configure(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "") || "/api";
    this.apiKey = apiKey;
    localStorage.setItem("risk-api-base", this.baseUrl);
    if (apiKey) localStorage.setItem("risk-api-key", apiKey);
    else localStorage.removeItem("risk-api-key");
  }

  async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(this.apiKey ? { "X-API-Key": this.apiKey } : {}),
        ...init?.headers
      }
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }));
      const message = body?.detail?.message || body?.detail || body?.error?.message || response.statusText;
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }
    return response.json() as Promise<T>;
  }

  websocketUrl(): string {
    const direct = this.baseUrl === "/api"
      ? `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/ws/live-alerts`
      : `${this.baseUrl.replace(/^http/, "ws")}/ws/live-alerts`;
    return this.apiKey ? `${direct}?api_key=${encodeURIComponent(this.apiKey)}` : direct;
  }
}

export const api = new ApiClient();
