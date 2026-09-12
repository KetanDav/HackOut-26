import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer
} from "recharts";
import {
  createUser, listUsers, placeOrder, listOrders,
  clearMarket, listTrades, getMarketSummary, listMarketRuns
} from "./api";

function Badge({ label, value, color }: { label: string; value: any; color: string }) {
  return (
    <div style={{ background: color, borderRadius: 12, padding: "16px 24px", minWidth: 140, textAlign: "center" }}>
      <div style={{ fontSize: 28, fontWeight: 700, color: "#fff" }}>{value}</div>
      <div style={{ fontSize: 12, color: "rgba(255,255,255,0.8)", marginTop: 4 }}>{label}</div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "8px 12px", borderRadius: 8,
  border: "1px solid #334155", background: "#0f172a",
  color: "#e2e8f0", boxSizing: "border-box", marginBottom: 12
};
const labelStyle: React.CSSProperties = {
  display: "block", marginBottom: 4, fontSize: 13, color: "#94a3b8"
};

export default function App() {
  const [tab, setTab] = useState<"dashboard" | "orders" | "market" | "users">("dashboard");
  const [summary, setSummary] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [orderForm, setOrderForm] = useState({ user_id: 1, order_type: "sell", energy_kwh: 1.0, price_per_kwh: 4.5, time_block: "2026-09-12 10:00", node_id: 1 });
  const [userForm, setUserForm] = useState({ name: "", email: "", role: "prosumer", node_id: 1, solar_capacity_kw: 0 });
  const [clearBlock, setClearBlock] = useState("2026-09-12 10:00");
  const [clearResult, setClearResult] = useState<any>(null);

  const refresh = async () => {
    try {
      const [s, t, o, u, r] = await Promise.all([
        getMarketSummary(), listTrades(), listOrders(), listUsers(), listMarketRuns()
      ]);
      setSummary(s.data); setTrades(t.data); setOrders(o.data); setUsers(u.data); setRuns(r.data);
    } catch {
      setMsg("Backend not reachable. Run: uvicorn main:app --reload (in /backend)");
    }
  };
  useEffect(() => { refresh(); }, []);

  const handlePlaceOrder = async () => {
    try { await placeOrder(orderForm); setMsg("Order placed!"); refresh(); }
    catch (e: any) { setMsg(e.response?.data?.detail || "Error placing order"); }
  };
  const handleCreateUser = async () => {
    try { await createUser(userForm); setMsg("User created!"); refresh(); }
    catch (e: any) { setMsg(e.response?.data?.detail || "Error creating user"); }
  };
  const handleClearMarket = async () => {
    try {
      const r = await clearMarket(clearBlock);
      setClearResult(r.data);
      setMsg("Cleared " + r.data.trades_count + " trades!");
      refresh();
    } catch (e: any) { setMsg(e.response?.data?.detail || "Error clearing market"); }
  };

  const priceChartData = trades.slice(0, 20).map((t: any) => ({
    name: "T" + t.id,
    "Market Price": t.clearing_price,
    Scarcity: t.price_scarcity,
    Loss: t.price_loss,
    Congestion: t.price_congestion,
  }));
  const supplyDemand = runs.slice(0, 8).reverse().map((r: any) => ({
    block: r.time_block.slice(11),
    Supply: r.total_sell_kwh,
    Demand: r.total_buy_kwh,
    Cleared: r.total_cleared_kwh,
  }));

  const tabs = ["dashboard", "orders", "market", "users"] as const;
  const dark = { background: "#0f172a", minHeight: "100vh", color: "#e2e8f0", fontFamily: "Inter, sans-serif" };
  const card: React.CSSProperties = { background: "#1e293b", borderRadius: 12, padding: 24, marginBottom: 24 };

  return (
    <div style={dark}>
      <div style={{ background: "#1e293b", padding: "16px 32px", display: "flex", alignItems: "center", gap: 16, borderBottom: "1px solid #334155" }}>
        <span style={{ fontSize: 24 }}>⚡</span>
        <div>
          <div style={{ fontWeight: 700, fontSize: 18, color: "#22c55e" }}>P2P Energy Market</div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>HackOut'26 — Grid-Aware Renewable Trading</div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          {tabs.map(t => (
            <button key={t} onClick={() => setTab(t)} style={{ padding: "8px 16px", borderRadius: 8, border: "none", cursor: "pointer", background: tab === t ? "#22c55e" : "#334155", color: tab === t ? "#000" : "#e2e8f0", fontWeight: tab === t ? 700 : 400, textTransform: "capitalize" }}>{t}</button>
          ))}
          <button onClick={refresh} style={{ padding: "8px 16px", borderRadius: 8, border: "none", cursor: "pointer", background: "#3b82f6", color: "#fff" }}>⟳ Refresh</button>
        </div>
      </div>

      {msg && <div style={{ background: "#166534", color: "#bbf7d0", padding: "8px 32px", fontSize: 14 }}>{msg} <button onClick={() => setMsg("")} style={{ marginLeft: 8, background: "none", border: "none", color: "#bbf7d0", cursor: "pointer" }}>x</button></div>}

      <div style={{ padding: 32 }}>

        {tab === "dashboard" && (
          <div>
            <h2 style={{ marginBottom: 24, color: "#22c55e" }}>Market Dashboard</h2>
            {summary && (
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 32 }}>
                <Badge label="Total Users" value={summary.total_users} color="#1d4ed8" />
                <Badge label="Open Sell Orders" value={summary.open_sell_orders} color="#15803d" />
                <Badge label="Open Buy Orders" value={summary.open_buy_orders} color="#b45309" />
                <Badge label="Total Trades" value={summary.total_trades} color="#7c3aed" />
                <Badge label="Cleared kWh" value={summary.total_cleared_kwh} color="#0f766e" />
                <Badge label="Avg Price Rs/kWh" value={summary.avg_final_price} color="#9f1239" />
              </div>
            )}
            {supplyDemand.length > 0 && (
              <div style={card}>
                <h3 style={{ marginBottom: 16, color: "#94a3b8" }}>Supply vs Demand vs Cleared (kWh per block)</h3>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={supplyDemand}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="block" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155" }} />
                    <Legend />
                    <Bar dataKey="Supply" fill="#22c55e" />
                    <Bar dataKey="Demand" fill="#3b82f6" />
                    <Bar dataKey="Cleared" fill="#f59e0b" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            {priceChartData.length > 0 && (
              <div style={card}>
                <h3 style={{ marginBottom: 16, color: "#94a3b8" }}>Price Decomposition per Trade (Rs/kWh — stacked)</h3>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={priceChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="name" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155" }} />
                    <Legend />
                    <Bar dataKey="Market Price" stackId="a" fill="#3b82f6" />
                    <Bar dataKey="Scarcity" stackId="a" fill="#f59e0b" />
                    <Bar dataKey="Loss" stackId="a" fill="#ef4444" />
                    <Bar dataKey="Congestion" stackId="a" fill="#7c3aed" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        {tab === "orders" && (
          <div>
            <h2 style={{ marginBottom: 24, color: "#22c55e" }}>Place Order</h2>
            <div style={{ ...card, maxWidth: 480 }}>
              {([["user_id","User ID","number"],["energy_kwh","Energy (kWh)","number"],["price_per_kwh","Price (Rs/kWh)","number"],["time_block","Time Block","text"],["node_id","Node ID (1-8)","number"]] as [string,string,string][]).map(([key,label,type]) => (
                <div key={key}>
                  <label style={labelStyle}>{label}</label>
                  <input type={type} value={(orderForm as any)[key]} style={inputStyle}
                    onChange={e => setOrderForm({ ...orderForm, [key]: type === "number" ? +e.target.value : e.target.value })} />
                </div>
              ))}
              <label style={labelStyle}>Order Type</label>
              <select value={orderForm.order_type} style={{ ...inputStyle }}
                onChange={e => setOrderForm({ ...orderForm, order_type: e.target.value })}>
                <option value="sell">Sell (Prosumer)</option>
                <option value="buy">Buy (Consumer)</option>
              </select>
              <button onClick={handlePlaceOrder} style={{ width: "100%", padding: 10, borderRadius: 8, border: "none", cursor: "pointer", background: "#22c55e", color: "#000", fontWeight: 700, fontSize: 15 }}>Place Order</button>
            </div>
            <h3 style={{ marginBottom: 12, color: "#94a3b8" }}>All Orders</h3>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead><tr style={{ background: "#1e293b" }}>
                  {["ID","User","Type","kWh","Price(Rs)","Remaining","Block","Node","Status"].map(h => (
                    <th key={h} style={{ padding: "10px 12px", color: "#94a3b8", borderBottom: "1px solid #334155", textAlign: "left" }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>{orders.map((o: any) => (
                  <tr key={o.id} style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={{ padding: "8px 12px" }}>{o.id}</td>
                    <td style={{ padding: "8px 12px" }}>{o.user_id}</td>
                    <td style={{ padding: "8px 12px", color: o.order_type === "sell" ? "#22c55e" : "#3b82f6", fontWeight: 600 }}>{o.order_type.toUpperCase()}</td>
                    <td style={{ padding: "8px 12px" }}>{o.energy_kwh}</td>
                    <td style={{ padding: "8px 12px" }}>{o.price_per_kwh}</td>
                    <td style={{ padding: "8px 12px" }}>{o.remaining_kwh}</td>
                    <td style={{ padding: "8px 12px" }}>{o.time_block}</td>
                    <td style={{ padding: "8px 12px" }}>{o.node_id}</td>
                    <td style={{ padding: "8px 12px", color: o.status === "open" ? "#22c55e" : "#94a3b8" }}>{o.status}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "market" && (
          <div>
            <h2 style={{ marginBottom: 24, color: "#22c55e" }}>Clear Market</h2>
            <div style={{ ...card, maxWidth: 480 }}>
              <label style={labelStyle}>Time Block</label>
              <input value={clearBlock} onChange={e => setClearBlock(e.target.value)} style={inputStyle} />
              <button onClick={handleClearMarket} style={{ width: "100%", padding: 10, borderRadius: 8, border: "none", cursor: "pointer", background: "#f59e0b", color: "#000", fontWeight: 700, fontSize: 15 }}>⚡ Run Market Clearing</button>
            </div>
            {clearResult && (
              <div style={card}>
                <h3 style={{ color: "#22c55e", marginBottom: 12 }}>Clearing Result — {clearResult.time_block}</h3>
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
                  <Badge label="Supply kWh" value={clearResult.total_sell_kwh} color="#15803d" />
                  <Badge label="Demand kWh" value={clearResult.total_buy_kwh} color="#1d4ed8" />
                  <Badge label="Cleared kWh" value={clearResult.total_cleared_kwh} color="#0f766e" />
                  <Badge label="Avg Rs/kWh" value={clearResult.avg_final_price} color="#9f1239" />
                  <Badge label="P_scarcity" value={clearResult.p_scarcity} color="#b45309" />
                  <Badge label="Trades" value={clearResult.trades_count} color="#7c3aed" />
                </div>
                {clearResult.trades?.map((t: any) => (
                  <div key={t.id} style={{ background: "#0f172a", borderRadius: 8, padding: 12, marginBottom: 8 }}>
                    <div style={{ fontWeight: 600 }}>Trade #{t.id} — {t.energy_kwh} kWh | Node {t.seller_node} → Node {t.buyer_node}</div>
                    <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 4 }}>
                      Final: <span style={{ color: "#22c55e", fontWeight: 700 }}>Rs {t.final_price}/kWh</span>
                      {" "}= market {t.clearing_price} + scarcity {t.price_scarcity} + loss {t.price_loss} + congestion {t.price_congestion}
                    </div>
                  </div>
                ))}
              </div>
            )}
            <h3 style={{ marginBottom: 12, color: "#94a3b8" }}>All Trades</h3>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead><tr style={{ background: "#1e293b" }}>
                  {["ID","Seller→Buyer","kWh","Market","Scarcity","Loss","Congestion","FINAL Rs/kWh","Block","Status"].map(h => (
                    <th key={h} style={{ padding: "10px 12px", color: "#94a3b8", borderBottom: "1px solid #334155", textAlign: "left" }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>{trades.map((t: any) => (
                  <tr key={t.id} style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={{ padding: "8px 12px" }}>{t.id}</td>
                    <td style={{ padding: "8px 12px" }}>{t.seller_id}→{t.buyer_id}</td>
                    <td style={{ padding: "8px 12px" }}>{t.energy_kwh}</td>
                    <td style={{ padding: "8px 12px" }}>{t.clearing_price}</td>
                    <td style={{ padding: "8px 12px", color: "#f59e0b" }}>{t.price_scarcity}</td>
                    <td style={{ padding: "8px 12px", color: "#ef4444" }}>{t.price_loss}</td>
                    <td style={{ padding: "8px 12px", color: "#7c3aed" }}>{t.price_congestion}</td>
                    <td style={{ padding: "8px 12px", color: "#22c55e", fontWeight: 700 }}>{t.final_price}</td>
                    <td style={{ padding: "8px 12px" }}>{t.time_block}</td>
                    <td style={{ padding: "8px 12px", color: "#94a3b8" }}>{t.status}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "users" && (
          <div>
            <h2 style={{ marginBottom: 24, color: "#22c55e" }}>Register User</h2>
            <div style={{ ...card, maxWidth: 480 }}>
              {([["name","Name","text"],["email","Email","text"],["node_id","Node ID (1-8)","number"],["solar_capacity_kw","Solar Capacity (kW)","number"]] as [string,string,string][]).map(([key,label,type]) => (
                <div key={key}>
                  <label style={labelStyle}>{label}</label>
                  <input type={type} value={(userForm as any)[key]} style={inputStyle}
                    onChange={e => setUserForm({ ...userForm, [key]: type === "number" ? +e.target.value : e.target.value })} />
                </div>
              ))}
              <label style={labelStyle}>Role</label>
              <select value={userForm.role} style={{ ...inputStyle }}
                onChange={e => setUserForm({ ...userForm, role: e.target.value })}>
                <option value="prosumer">Prosumer (has solar, can sell)</option>
                <option value="consumer">Consumer (buys only)</option>
                <option value="both">Both</option>
              </select>
              <button onClick={handleCreateUser} style={{ width: "100%", padding: 10, borderRadius: 8, border: "none", cursor: "pointer", background: "#3b82f6", color: "#fff", fontWeight: 700, fontSize: 15 }}>Register User</button>
            </div>
            <h3 style={{ marginBottom: 12, color: "#94a3b8" }}>Registered Users</h3>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead><tr style={{ background: "#1e293b" }}>
                  {["ID","Name","Email","Role","Node ID","Solar kW"].map(h => (
                    <th key={h} style={{ padding: "10px 12px", color: "#94a3b8", borderBottom: "1px solid #334155", textAlign: "left" }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>{users.map((u: any) => (
                  <tr key={u.id} style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={{ padding: "8px 12px" }}>{u.id}</td>
                    <td style={{ padding: "8px 12px", fontWeight: 600 }}>{u.name}</td>
                    <td style={{ padding: "8px 12px", color: "#94a3b8" }}>{u.email}</td>
                    <td style={{ padding: "8px 12px", color: u.role === "prosumer" ? "#22c55e" : u.role === "both" ? "#f59e0b" : "#3b82f6" }}>{u.role}</td>
                    <td style={{ padding: "8px 12px" }}>{u.node_id}</td>
                    <td style={{ padding: "8px 12px" }}>{u.solar_capacity_kw}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}