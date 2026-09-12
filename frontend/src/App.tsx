import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, AreaChart, Area, LineChart, Line, ReferenceLine
} from "recharts";
import {
  createUser, listUsers, placeOrder, listOrders,
  clearMarket, listTrades, getMarketSummary, listMarketRuns,
  getFeederState, resetFeeder, injectCongestion,
  runDemoBenchmark, getForecastDay, getForecastScenario
} from "./api";
import FeederMap from "./FeederMap";

function Badge({ label, value, color }: { label: string; value: any; color: string }) {
  return (
    <div style={{ background: color, borderRadius: 12, padding: "14px 20px", minWidth: 130, textAlign: "center" }}>
      <div style={{ fontSize: 24, fontWeight: 700, color: "#fff" }}>{value}</div>
      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.8)", marginTop: 4 }}>{label}</div>
    </div>
  );
}

const inp: React.CSSProperties = { width:"100%", padding:"8px 12px", borderRadius:8, border:"1px solid #334155", background:"#0f172a", color:"#e2e8f0", boxSizing:"border-box", marginBottom:12 };
const lbl: React.CSSProperties = { display:"block", marginBottom:4, fontSize:12, color:"#94a3b8" };
const card: React.CSSProperties = { background:"#1e293b", borderRadius:12, padding:20, marginBottom:20 };

export default function App() {
  const [tab, setTab] = useState<"dashboard"|"feeder"|"benchmark"|"forecast"|"orders"|"market"|"users">("dashboard");
  const [summary, setSummary] = useState<any>(null);
  const [trades, setTrades]   = useState<any[]>([]);
  const [orders, setOrders]   = useState<any[]>([]);
  const [users, setUsers]     = useState<any[]>([]);
  const [runs, setRuns]       = useState<any[]>([]);
  const [feeder, setFeeder]   = useState<any>(null);
  const [msg, setMsg]         = useState("");
  const [msgOk, setMsgOk]     = useState(true);
  const [clearResult, setClearResult] = useState<any>(null);
  const [benchResult, setBenchResult] = useState<any>(null);
  const [benchLoading, setBenchLoading] = useState(false);
  const [forecastData, setForecastData]   = useState<any[]>([]);
  const [forecastCloudy, setForecastCloudy] = useState<any[]>([]);
  const [cloudFactor, setCloudFactor] = useState(0.2);
  const [orderForm, setOrderForm]   = useState({ user_id:1, order_type:"sell", energy_kwh:2.0, price_per_kwh:0, time_block:"2026-09-13 10:00", node_id:4 });
  const [userForm, setUserForm]     = useState({ name:"", email:"", role:"prosumer", node_id:1, solar_capacity_kw:0 });
  const [clearBlock, setClearBlock] = useState("2026-09-13 10:00");
  const [congLine, setCongLine]     = useState("L3-7");
  const [congKw, setCongKw]         = useState(25);

  const notify = (m: string, ok = true) => { setMsg(m); setMsgOk(ok); };

  const refresh = async () => {
    try {
      const [s, t, o, u, r, f] = await Promise.all([
        getMarketSummary(), listTrades(), listOrders(), listUsers(), listMarketRuns(), getFeederState()
      ]);
      setSummary(s.data); setTrades(t.data); setOrders(o.data); setUsers(u.data); setRuns(r.data); setFeeder(f.data);
    } catch { notify("Backend offline — run: uvicorn main:app --reload", false); }
  };

  const loadForecast = async () => {
    try {
      const [clear, cloudy] = await Promise.all([
        getForecastDay("2026-09-13", cloudFactor),
        getForecastDay("2026-09-13", 0.75),
      ]);
      const peakHours = (arr: any[]) => arr.filter((i: any) => i.hour >= 6 && i.hour <= 20);
      setForecastData(peakHours(clear.data.intervals));
      setForecastCloudy(peakHours(cloudy.data.intervals));
    } catch { notify("Forecast load failed", false); }
  };

  useEffect(() => { refresh(); }, []);
  useEffect(() => { if (tab === "forecast") loadForecast(); }, [tab, cloudFactor]);

  const handlePlaceOrder  = async () => { try { await placeOrder(orderForm); notify("Declaration submitted!"); refresh(); } catch (e: any) { notify(e.response?.data?.detail || "Error", false); } };
  const handleCreateUser  = async () => { try { await createUser(userForm); notify("User registered!"); refresh(); } catch (e: any) { notify(e.response?.data?.detail || "Error", false); } };
  const handleClear       = async () => { try { const r = await clearMarket(clearBlock); setClearResult(r.data); setFeeder(r.data.feeder_state); notify(`Allocated ${r.data.trades_count} trades`); } catch (e: any) { notify(e.response?.data?.detail || "Error", false); } };
  const handleResetFeeder = async () => { const r = await resetFeeder(); setFeeder(r.data.state); notify("Feeder reset"); };
  const handleInjectCong  = async () => { const r = await injectCongestion(congLine, congKw); setFeeder(r.data.state); notify(`${congLine}: ${(r.data.utilisation*100).toFixed(0)}% ${r.data.is_congested ? "CONGESTED" : ""}`); };
  const handleBenchmark   = async () => { setBenchLoading(true); try { const r = await runDemoBenchmark(); setBenchResult(r.data); notify("Benchmark complete"); } catch { notify("Benchmark failed", false); } setBenchLoading(false); };

  const priceChart  = trades.slice(0,20).map((t:any) => ({ name:"T"+t.id, P_base:t.clearing_price, P_scarcity:t.price_scarcity, P_loss:t.price_loss, P_congestion:t.price_congestion }));
  const supplyChart = runs.slice(0,8).reverse().map((r:any) => ({ block:r.time_block.slice(11), Supply:r.total_sell_kwh, Demand:r.total_buy_kwh, Cleared:r.total_cleared_kwh }));
  const TABS = ["dashboard","feeder","benchmark","forecast","orders","market","users"] as const;

  // Benchmark chart data
  const benchMetrics = benchResult ? [
    { metric:"Consumer Price (Rs/kWh)", A: benchResult.results.A.consumer_avg_price_rs_kwh, B: benchResult.results.B.consumer_avg_price_rs_kwh, C: benchResult.results.C.consumer_avg_price_rs_kwh },
    { metric:"Prosumer Price (Rs/kWh)", A: benchResult.results.A.prosumer_avg_price_rs_kwh, B: benchResult.results.B.prosumer_avg_price_rs_kwh, C: benchResult.results.C.prosumer_avg_price_rs_kwh },
    { metric:"P2P Share %",             A: benchResult.results.A.p2p_share_pct,              B: benchResult.results.B.p2p_share_pct,              C: benchResult.results.C.p2p_share_pct },
    { metric:"Network Losses (kW)",     A: benchResult.results.A.network_loss_kw,            B: benchResult.results.B.network_loss_kw,            C: benchResult.results.C.network_loss_kw },
    { metric:"Congestion Violations",   A: benchResult.results.A.congestion_violations,      B: benchResult.results.B.congestion_violations,      C: benchResult.results.C.congestion_violations },
  ] : [];

  // Forecast chart — merge clear and cloudy by time block
  const forecastChart = forecastData.map((d: any, i: number) => ({
    block: d.time_block.slice(11,16),
    "Solar (clear)":    d.solar_kwh,
    "Load":             d.load_kwh,
    "Tradable (clear)": d.tradable_kwh,
    "Solar (cloudy)":   forecastCloudy[i]?.solar_kwh ?? 0,
    "Tradable (cloudy)":forecastCloudy[i]?.tradable_kwh ?? 0,
  }));

  return (
    <div style={{ fontFamily:"Inter,sans-serif", background:"#0f172a", minHeight:"100vh", color:"#e2e8f0" }}>
      <div style={{ background:"#1e293b", padding:"13px 24px", display:"flex", alignItems:"center", gap:12, borderBottom:"1px solid #334155", flexWrap:"wrap" }}>
        <span style={{ fontSize:20 }}>⚡</span>
        <div>
          <div style={{ fontWeight:700, fontSize:16, color:"#22c55e" }}>P2P Energy Market</div>
          <div style={{ fontSize:10, color:"#94a3b8" }}>HackOut'26 · Grid-Aware Centralised Pricing & Allocation · v2.0</div>
        </div>
        <div style={{ marginLeft:"auto", display:"flex", gap:5, flexWrap:"wrap" }}>
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} style={{ padding:"6px 12px", borderRadius:8, border:"none", cursor:"pointer", background:tab===t?"#22c55e":"#334155", color:tab===t?"#000":"#e2e8f0", fontWeight:tab===t?700:400, fontSize:13, textTransform:"capitalize" }}>
              {t==="benchmark"?"📊 Benchmark":t==="forecast"?"🌤 Forecast":t==="feeder"?"⚡ Feeder":t}
            </button>
          ))}
          <button onClick={refresh} style={{ padding:"6px 12px", borderRadius:8, border:"none", cursor:"pointer", background:"#3b82f6", color:"#fff", fontSize:13 }}>⟳</button>
        </div>
      </div>

      {msg && <div style={{ background:msgOk?"#166534":"#7f1d1d", color:msgOk?"#bbf7d0":"#fca5a5", padding:"7px 24px", fontSize:13, display:"flex", justifyContent:"space-between" }}><span>{msg}</span><button onClick={()=>setMsg("")} style={{ background:"none", border:"none", color:"inherit", cursor:"pointer" }}>x</button></div>}

      <div style={{ padding:24 }}>

        {/* ── DASHBOARD ── */}
        {tab==="dashboard" && <div>
          <h2 style={{ marginBottom:18, color:"#22c55e" }}>Market Dashboard</h2>
          {summary && <div style={{ display:"flex", gap:10, flexWrap:"wrap", marginBottom:20 }}>
            <Badge label="Users"        value={summary.total_users}       color="#1d4ed8" />
            <Badge label="Open Supply"  value={summary.open_sell_orders}  color="#15803d" />
            <Badge label="Open Demand"  value={summary.open_buy_orders}   color="#b45309" />
            <Badge label="Total Trades" value={summary.total_trades}      color="#7c3aed" />
            <Badge label="Cleared kWh"  value={summary.total_cleared_kwh} color="#0f766e" />
            <Badge label="Avg Rs/kWh"   value={summary.avg_final_price}   color="#9f1239" />
          </div>}
          {supplyChart.length>0 && <div style={card}>
            <h3 style={{ marginBottom:12, color:"#94a3b8", fontSize:13 }}>Supply / Demand / Allocated (kWh per block)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={supplyChart}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="block" stroke="#94a3b8"/><YAxis stroke="#94a3b8"/><Tooltip contentStyle={{ background:"#1e293b",border:"1px solid #334155" }}/><Legend/><Bar dataKey="Supply" fill="#22c55e"/><Bar dataKey="Demand" fill="#3b82f6"/><Bar dataKey="Cleared" fill="#f59e0b"/></BarChart>
            </ResponsiveContainer>
          </div>}
          {priceChart.length>0 && <div style={card}>
            <h3 style={{ marginBottom:12, color:"#94a3b8", fontSize:13 }}>Price Decomposition per Transaction (P_final = P_base + P_scarcity + P_loss + P_congestion)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={priceChart}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="name" stroke="#94a3b8"/><YAxis stroke="#94a3b8"/><Tooltip contentStyle={{ background:"#1e293b",border:"1px solid #334155" }}/><Legend/>
                <Bar dataKey="P_base"       stackId="a" fill="#3b82f6"/>
                <Bar dataKey="P_scarcity"   stackId="a" fill="#f59e0b"/>
                <Bar dataKey="P_loss"       stackId="a" fill="#ef4444"/>
                <Bar dataKey="P_congestion" stackId="a" fill="#7c3aed"/>
              </BarChart>
            </ResponsiveContainer>
          </div>}
        </div>}

        {/* ── FEEDER ── */}
        {tab==="feeder" && <div>
          <h2 style={{ marginBottom:18, color:"#22c55e" }}>Grid Digital Twin</h2>
          <div style={card}><FeederMap feeder={feeder}/></div>
          <div style={{ display:"flex", gap:16, flexWrap:"wrap" }}>
            <div style={{ ...card, flex:1, minWidth:220 }}>
              <h3 style={{ marginBottom:12, color:"#94a3b8", fontSize:13 }}>Demo Controls</h3>
              <label style={lbl}>Inject congestion on line</label>
              <select value={congLine} onChange={e=>setCongLine(e.target.value)} style={{ ...inp }}>
                {["L1-2","L1-3","L2-4","L2-5","L3-6","L3-7","L7-8"].map(l=><option key={l} value={l}>{l}</option>)}
              </select>
              <label style={lbl}>Load (kW)</label>
              <input type="number" value={congKw} onChange={e=>setCongKw(+e.target.value)} style={inp}/>
              <button onClick={handleInjectCong} style={{ width:"100%", padding:9, borderRadius:8, border:"none", cursor:"pointer", background:"#ef4444", color:"#fff", fontWeight:700, marginBottom:8 }}>Inject Congestion</button>
              <button onClick={handleResetFeeder} style={{ width:"100%", padding:9, borderRadius:8, border:"none", cursor:"pointer", background:"#334155", color:"#e2e8f0", fontWeight:600 }}>Reset Flows</button>
            </div>
            <div style={{ ...card, flex:2, minWidth:280 }}>
              <h3 style={{ marginBottom:12, color:"#94a3b8", fontSize:13 }}>Line Detail</h3>
              <div style={{ overflowX:"auto" }}>
                <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
                  <thead><tr style={{ background:"#0f172a" }}>{["Line","Cap kW","Flow kW","Loss kW","Util %","Status"].map(h=><th key={h} style={{ padding:"7px 10px", color:"#94a3b8", textAlign:"left", borderBottom:"1px solid #334155" }}>{h}</th>)}</tr></thead>
                  <tbody>{feeder?.lines.map((l:any)=>(
                    <tr key={l.line_id} style={{ borderBottom:"1px solid #1e293b" }}>
                      <td style={{ padding:"6px 10px", fontWeight:600 }}>{l.line_id}</td>
                      <td style={{ padding:"6px 10px" }}>{l.capacity_kw}</td>
                      <td style={{ padding:"6px 10px" }}>{l.flow_kw}</td>
                      <td style={{ padding:"6px 10px", color:"#f59e0b" }}>{l.loss_kw}</td>
                      <td style={{ padding:"6px 10px", color:l.is_congested?"#ef4444":l.utilisation>0?"#22c55e":"#64748b" }}>{(l.utilisation*100).toFixed(1)}%</td>
                      <td style={{ padding:"6px 10px", color:l.is_congested?"#ef4444":"#22c55e", fontWeight:600 }}>{l.is_congested?"CONGESTED":l.flow_kw>0?"Active":"Idle"}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
          </div>
        </div>}

        {/* ── BENCHMARK ── */}
        {tab==="benchmark" && <div>
          <h2 style={{ marginBottom:8, color:"#22c55e" }}>Benchmark Comparison</h2>
          <p style={{ color:"#94a3b8", fontSize:13, marginBottom:18 }}>
            Same scenario, three modes: Grid-only (A) vs Naive P2P (B) vs Grid-aware P2P (C).
          </p>
          <button onClick={handleBenchmark} disabled={benchLoading} style={{ padding:"10px 24px", borderRadius:8, border:"none", cursor:"pointer", background:"#22c55e", color:"#000", fontWeight:700, marginBottom:20, fontSize:14 }}>
            {benchLoading ? "Running..." : "Run Demo Benchmark (3 prosumers, 4 consumers)"}
          </button>

          {benchResult && <>
            {/* Summary cards per mode */}
            <div style={{ display:"flex", gap:16, flexWrap:"wrap", marginBottom:20 }}>
              {(["A","B","C"] as const).map(m => {
                const r = benchResult.results[m];
                const colors = { A:"#1d4ed8", B:"#b45309", C:"#15803d" };
                const labels = { A:"Grid-only", B:"Naive P2P", C:"Grid-aware P2P" };
                return (
                  <div key={m} style={{ flex:1, minWidth:200, background: colors[m], borderRadius:12, padding:16 }}>
                    <div style={{ fontSize:13, fontWeight:700, color:"#fff", marginBottom:10 }}>Mode {m}: {labels[m]}</div>
                    <div style={{ fontSize:12, color:"rgba(255,255,255,0.85)", lineHeight:1.8 }}>
                      Consumer: <b>Rs {r.consumer_avg_price_rs_kwh}/kWh</b><br/>
                      Prosumer: <b>Rs {r.prosumer_avg_price_rs_kwh}/kWh</b><br/>
                      P2P share: <b>{r.p2p_share_pct}%</b><br/>
                      Losses: <b>{r.network_loss_kw} kW</b><br/>
                      Congestion violations: <b>{r.congestion_violations}</b>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Side-by-side bar chart */}
            <div style={card}>
              <h3 style={{ marginBottom:12, color:"#94a3b8", fontSize:13 }}>Side-by-side Comparison</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={benchMetrics} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155"/>
                  <XAxis type="number" stroke="#94a3b8"/>
                  <YAxis type="category" dataKey="metric" stroke="#94a3b8" width={160} tick={{ fontSize:11 }}/>
                  <Tooltip contentStyle={{ background:"#1e293b", border:"1px solid #334155" }}/>
                  <Legend/>
                  <Bar dataKey="A" name="A: Grid-only"     fill="#3b82f6"/>
                  <Bar dataKey="B" name="B: Naive P2P"     fill="#f59e0b"/>
                  <Bar dataKey="C" name="C: Grid-aware P2P" fill="#22c55e"/>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Delta summary */}
            <div style={card}>
              <h3 style={{ marginBottom:12, color:"#94a3b8", fontSize:13 }}>Grid-aware P2P (C) vs Grid-only (A) — Deltas</h3>
              <div style={{ display:"flex", gap:16, flexWrap:"wrap" }}>
                {Object.entries(benchResult.deltas_C_vs_A).map(([k,v]:any) => (
                  <div key={k} style={{ background:"#0f172a", borderRadius:8, padding:"12px 16px", minWidth:160 }}>
                    <div style={{ fontSize:11, color:"#94a3b8", marginBottom:4 }}>{k.replace(/_/g," ")}</div>
                    <div style={{ fontSize:16, fontWeight:700, color:"#22c55e" }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>
          </>}
        </div>}

        {/* ── FORECAST ── */}
        {tab==="forecast" && <div>
          <h2 style={{ marginBottom:8, color:"#22c55e" }}>Solar & Load Forecast</h2>
          <p style={{ color:"#94a3b8", fontSize:13, marginBottom:16 }}>
            XGBoost model trained on 30 days of synthetic household data.
            TradableEnergy = max(0, ForecastSurplus - k x ForecastError) — conservative commitment.
          </p>
          <div style={{ display:"flex", alignItems:"center", gap:16, marginBottom:20 }}>
            <label style={{ ...lbl, marginBottom:0 }}>Cloud factor (0=clear, 1=overcast):</label>
            <input type="range" min={0} max={1} step={0.05} value={cloudFactor}
              onChange={e=>setCloudFactor(+e.target.value)}
              style={{ width:180, accentColor:"#22c55e" }}/>
            <span style={{ color:"#22c55e", fontWeight:700, minWidth:32 }}>{cloudFactor.toFixed(2)}</span>
          </div>

          {forecastChart.length>0 && <>
            <div style={card}>
              <h3 style={{ marginBottom:12, color:"#94a3b8", fontSize:13 }}>
                Solar Generation vs Load (kWh per 15-min block) — clear sky vs overcast
              </h3>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={forecastChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155"/>
                  <XAxis dataKey="block" stroke="#94a3b8" interval={7} tick={{ fontSize:11 }}/>
                  <YAxis stroke="#94a3b8"/>
                  <Tooltip contentStyle={{ background:"#1e293b", border:"1px solid #334155" }}/>
                  <Legend/>
                  <Area type="monotone" dataKey="Solar (clear)"  fill="#22c55e" stroke="#22c55e" fillOpacity={0.3}/>
                  <Area type="monotone" dataKey="Solar (cloudy)" fill="#64748b" stroke="#64748b" fillOpacity={0.2}/>
                  <Area type="monotone" dataKey="Load"           fill="#3b82f6" stroke="#3b82f6" fillOpacity={0.2}/>
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div style={card}>
              <h3 style={{ marginBottom:12, color:"#94a3b8", fontSize:13 }}>
                Conservative TradableEnergy (kWh) — what the engine commits to the market
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={forecastChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155"/>
                  <XAxis dataKey="block" stroke="#94a3b8" interval={7} tick={{ fontSize:11 }}/>
                  <YAxis stroke="#94a3b8"/>
                  <Tooltip contentStyle={{ background:"#1e293b", border:"1px solid #334155" }}/>
                  <Legend/>
                  <Area type="monotone" dataKey="Tradable (clear)"  fill="#22c55e" stroke="#22c55e" fillOpacity={0.4}/>
                  <Area type="monotone" dataKey="Tradable (cloudy)" fill="#64748b" stroke="#64748b" fillOpacity={0.3}/>
                  <ReferenceLine y={0} stroke="#334155"/>
                </AreaChart>
              </ResponsiveContainer>
              <p style={{ fontSize:12, color:"#64748b", marginTop:8 }}>
                During cloud cover (overcast), TradableEnergy drops to 0 to prevent over-commitment.
                The system only offers surplus it is confident exists.
              </p>
            </div>
          </>}
        </div>}

        {/* ── ORDERS ── */}
        {tab==="orders" && <div>
          <h2 style={{ marginBottom:18, color:"#22c55e" }}>Submit Declaration</h2>
          <div style={{ ...card, maxWidth:440 }}>
            <p style={{ fontSize:12, color:"#94a3b8", marginBottom:12 }}>Prosumers declare surplus. Consumers declare requirements. Engine prices automatically.</p>
            {([["user_id","User ID","number"],["energy_kwh","Energy (kWh)","number"],["time_block","Time Block","text"],["node_id","Node ID (1-8)","number"]] as [string,string,string][]).map(([key,label,type])=>(
              <div key={key}><label style={lbl}>{label}</label><input type={type} value={(orderForm as any)[key]} style={inp} onChange={e=>setOrderForm({ ...orderForm,[key]:type==="number"?+e.target.value:e.target.value })}/></div>
            ))}
            <label style={lbl}>Type</label>
            <select value={orderForm.order_type} style={{ ...inp }} onChange={e=>setOrderForm({ ...orderForm,order_type:e.target.value })}>
              <option value="sell">Supply (Prosumer)</option>
              <option value="buy">Demand (Consumer)</option>
            </select>
            <button onClick={handlePlaceOrder} style={{ width:"100%", padding:9, borderRadius:8, border:"none", cursor:"pointer", background:"#22c55e", color:"#000", fontWeight:700 }}>Submit Declaration</button>
          </div>
          <h3 style={{ marginBottom:10, color:"#94a3b8" }}>All Declarations</h3>
          <div style={{ overflowX:"auto" }}>
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
              <thead><tr style={{ background:"#1e293b" }}>{["ID","User","Type","kWh","Remaining","Block","Node","Status"].map(h=><th key={h} style={{ padding:"8px 10px", color:"#94a3b8", textAlign:"left", borderBottom:"1px solid #334155" }}>{h}</th>)}</tr></thead>
              <tbody>{orders.map((o:any)=>(
                <tr key={o.id} style={{ borderBottom:"1px solid #1e293b" }}>
                  <td style={{ padding:"6px 10px" }}>{o.id}</td>
                  <td style={{ padding:"6px 10px" }}>{o.user_id}</td>
                  <td style={{ padding:"6px 10px", color:o.order_type==="sell"?"#22c55e":"#3b82f6", fontWeight:600 }}>{o.order_type==="sell"?"SUPPLY":"DEMAND"}</td>
                  <td style={{ padding:"6px 10px" }}>{o.energy_kwh}</td>
                  <td style={{ padding:"6px 10px" }}>{o.remaining_kwh}</td>
                  <td style={{ padding:"6px 10px" }}>{o.time_block}</td>
                  <td style={{ padding:"6px 10px" }}>{o.node_id}</td>
                  <td style={{ padding:"6px 10px", color:o.status==="open"?"#22c55e":"#94a3b8" }}>{o.status}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>}

        {/* ── MARKET ── */}
        {tab==="market" && <div>
          <h2 style={{ marginBottom:18, color:"#22c55e" }}>Run Allocation Engine</h2>
          <div style={{ ...card, maxWidth:440 }}>
            <label style={lbl}>Time Block</label>
            <input value={clearBlock} onChange={e=>setClearBlock(e.target.value)} style={inp}/>
            <button onClick={handleClear} style={{ width:"100%", padding:9, borderRadius:8, border:"none", cursor:"pointer", background:"#f59e0b", color:"#000", fontWeight:700 }}>Run Pricing & Allocation Engine</button>
          </div>
          {clearResult && <div style={card}>
            <h3 style={{ color:"#22c55e", marginBottom:12 }}>Allocation Result — {clearResult.time_block}</h3>
            <div style={{ display:"flex", gap:10, flexWrap:"wrap", marginBottom:14 }}>
              <Badge label="Supply kWh"   value={clearResult.total_supply_kwh}    color="#15803d"/>
              <Badge label="Demand kWh"   value={clearResult.total_demand_kwh}    color="#1d4ed8"/>
              <Badge label="Allocated"    value={clearResult.total_allocated_kwh} color="#0f766e"/>
              <Badge label="Exported kWh" value={clearResult.surplus_exported_kwh}color="#64748b"/>
              <Badge label="Avg Rs/kWh"   value={clearResult.avg_final_price}     color="#9f1239"/>
              <Badge label="P_scarcity"   value={clearResult.p_scarcity}          color="#b45309"/>
            </div>
            {clearResult.trades?.map((t:any)=>(
              <div key={t.id} style={{ background:"#0f172a", borderRadius:8, padding:12, marginBottom:8 }}>
                <div style={{ fontWeight:600 }}>#{t.id} &mdash; {t.energy_kwh} kWh | Node {t.seller_node} {"->"} Node {t.buyer_node}</div>
                <div style={{ fontSize:12, color:"#94a3b8", marginTop:4 }}>
                  P_final: <span style={{ color:"#22c55e", fontWeight:700 }}>Rs {t.final_price}/kWh</span>
                  {" = "} P_base {t.p_base} + P_scarcity {t.p_scarcity} + P_loss {t.p_loss} + P_cong {t.p_congestion}
                </div>
              </div>
            ))}
            {clearResult.feeder_state && <div style={{ marginTop:14 }}><h4 style={{ color:"#94a3b8", marginBottom:8, fontSize:13 }}>Post-Allocation Feeder</h4><FeederMap feeder={clearResult.feeder_state}/></div>}
          </div>}
          <h3 style={{ marginBottom:10, color:"#94a3b8" }}>All Transactions</h3>
          <div style={{ overflowX:"auto" }}>
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
              <thead><tr style={{ background:"#1e293b" }}>{["ID","Prosumer->Consumer","kWh","P_base","P_scar","P_loss","P_cong","FINAL","Block"].map(h=><th key={h} style={{ padding:"7px 10px", color:"#94a3b8", textAlign:"left", borderBottom:"1px solid #334155" }}>{h}</th>)}</tr></thead>
              <tbody>{trades.map((t:any)=>(
                <tr key={t.id} style={{ borderBottom:"1px solid #1e293b" }}>
                  <td style={{ padding:"6px 10px" }}>{t.id}</td>
                  <td style={{ padding:"6px 10px" }}>{t.seller_id}{"->"}{t.buyer_id}</td>
                  <td style={{ padding:"6px 10px" }}>{t.energy_kwh}</td>
                  <td style={{ padding:"6px 10px" }}>{t.clearing_price}</td>
                  <td style={{ padding:"6px 10px", color:"#f59e0b" }}>{t.price_scarcity}</td>
                  <td style={{ padding:"6px 10px", color:"#ef4444" }}>{t.price_loss}</td>
                  <td style={{ padding:"6px 10px", color:"#7c3aed" }}>{t.price_congestion}</td>
                  <td style={{ padding:"6px 10px", color:"#22c55e", fontWeight:700 }}>{t.final_price}</td>
                  <td style={{ padding:"6px 10px" }}>{t.time_block}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>}

        {/* ── USERS ── */}
        {tab==="users" && <div>
          <h2 style={{ marginBottom:18, color:"#22c55e" }}>Register Participant</h2>
          <div style={{ ...card, maxWidth:440 }}>
            {([["name","Name","text"],["email","Email","text"],["node_id","Node ID (1-8)","number"],["solar_capacity_kw","Solar kW","number"]] as [string,string,string][]).map(([key,label,type])=>(
              <div key={key}><label style={lbl}>{label}</label><input type={type} value={(userForm as any)[key]} style={inp} onChange={e=>setUserForm({ ...userForm,[key]:type==="number"?+e.target.value:e.target.value })}/></div>
            ))}
            <label style={lbl}>Role</label>
            <select value={userForm.role} style={{ ...inp }} onChange={e=>setUserForm({ ...userForm,role:e.target.value })}>
              <option value="prosumer">Prosumer (solar, can supply)</option>
              <option value="consumer">Consumer (needs energy)</option>
              <option value="both">Both</option>
            </select>
            <button onClick={handleCreateUser} style={{ width:"100%", padding:9, borderRadius:8, border:"none", cursor:"pointer", background:"#3b82f6", color:"#fff", fontWeight:700 }}>Register</button>
          </div>
          <h3 style={{ marginBottom:10, color:"#94a3b8" }}>Participants</h3>
          <div style={{ overflowX:"auto" }}>
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
              <thead><tr style={{ background:"#1e293b" }}>{["ID","Name","Email","Role","Node","Solar kW"].map(h=><th key={h} style={{ padding:"7px 10px", color:"#94a3b8", textAlign:"left", borderBottom:"1px solid #334155" }}>{h}</th>)}</tr></thead>
              <tbody>{users.map((u:any)=>(
                <tr key={u.id} style={{ borderBottom:"1px solid #1e293b" }}>
                  <td style={{ padding:"6px 10px" }}>{u.id}</td>
                  <td style={{ padding:"6px 10px", fontWeight:600 }}>{u.name}</td>
                  <td style={{ padding:"6px 10px", color:"#94a3b8" }}>{u.email}</td>
                  <td style={{ padding:"6px 10px", color:u.role==="prosumer"?"#22c55e":u.role==="both"?"#f59e0b":"#3b82f6" }}>{u.role}</td>
                  <td style={{ padding:"6px 10px" }}>{u.node_id}</td>
                  <td style={{ padding:"6px 10px" }}>{u.solar_capacity_kw}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>}

      </div>
    </div>
  );
}