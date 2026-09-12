import axios from "axios";

const BASE = "http://localhost:8000";
export const api = axios.create({ baseURL: BASE });

// Users
export const createUser = (data: any) => api.post("/users/", data);
export const listUsers  = () => api.get("/users/");

// Declarations
export const placeOrder  = (data: any) => api.post("/orders/", data);
export const listOrders  = (params?: any) => api.get("/orders/", { params });

// Allocation Engine
export const clearMarket     = (tb: string) => api.post(`/market/clear/${encodeURIComponent(tb)}`);
export const listTrades      = (tb?: string) => api.get("/market/trades", { params: tb ? { time_block: tb } : {} });
export const getMarketSummary= () => api.get("/market/summary");
export const listMarketRuns  = () => api.get("/market/runs");

// Grid Digital Twin
export const getFeederState    = () => api.get("/market/feeder");
export const getFeederPath     = (src: number, dst: number) => api.get("/market/feeder/path", { params: { src, dst } });
export const resetFeeder       = () => api.post("/market/feeder/reset");
export const injectCongestion  = (lineId: string, loadKw?: number) =>
  api.post("/market/feeder/inject_congestion", null, { params: { line_id: lineId, load_kw: loadKw ?? 18 } });

// Benchmark
export const runDemoBenchmark  = () => api.get("/benchmark/demo");
export const runBenchmark      = (data: any) => api.post("/benchmark/run", data);

// Forecast
export const getForecastDay    = (date: string, cloudFactor?: number, capacityKw?: number) =>
  api.get("/forecast/day", { params: { date, cloud_factor: cloudFactor ?? 0.2, capacity_kw: capacityKw ?? 5 } });
export const getForecastScenario = () => api.get("/forecast/scenario");