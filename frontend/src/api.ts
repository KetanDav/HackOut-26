import axios from "axios";

const BASE = "http://localhost:8000";

export const api = axios.create({ baseURL: BASE });

// Users
export const createUser = (data: any) => api.post("/users/", data);
export const listUsers = () => api.get("/users/");

// Orders
export const placeOrder = (data: any) => api.post("/orders/", data);
export const listOrders = (params?: any) => api.get("/orders/", { params });

// Market
export const clearMarket = (timeBlock: string) =>
  api.post(`/market/clear/${encodeURIComponent(timeBlock)}`);
export const listTrades = (timeBlock?: string) =>
  api.get("/market/trades", { params: timeBlock ? { time_block: timeBlock } : {} });
export const getMarketSummary = () => api.get("/market/summary");
export const listMarketRuns = () => api.get("/market/runs");
