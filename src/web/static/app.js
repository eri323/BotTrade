const $ = (id) => document.getElementById(id);
const fmtUsd = (n) => "$" + Number(n).toLocaleString("en-US", { maximumFractionDigits: 2 });
const fmtPct = (n) => (n >= 0 ? "+" : "") + Number(n).toFixed(2) + "%";
const cls = (n) => (n >= 0 ? "pos" : "neg");

async function getJSON(url) { const r = await fetch(url); return r.json(); }
async function post(url) { return fetch(url, { method: "POST" }); }

let equityChart = null;

async function refresh() {
  const status = await getJSON("/api/status");
  $("mode").textContent = status.mode;
  $("state").textContent = status.running ? "● Corriendo" : "● Detenido";
  $("state").className = "state " + (status.running ? "on" : "off");
  $("btn-start").disabled = status.running;
  $("btn-stop").disabled = !status.running;

  const acct = await getJSON("/api/account");
  $("portfolio").textContent = fmtUsd(acct.portfolio_value);
  $("cash").textContent = fmtUsd(acct.cash);
  const today = acct.last_equity ? ((acct.portfolio_value - acct.last_equity) / acct.last_equity) * 100 : 0;
  $("pnl-today").textContent = fmtPct(today);
  $("pnl-today").className = "card-value " + cls(today);

  const metrics = await getJSON("/api/metrics");
  $("pnl-total").textContent = fmtPct(metrics.total_return_pct);
  $("pnl-total").className = "card-value " + cls(metrics.total_return_pct);
  $("metrics-body").innerHTML = `
    <tr><td>Win rate</td><td>${metrics.win_rate_pct}%</td></tr>
    <tr><td>Profit factor</td><td>${metrics.profit_factor ?? "∞"}</td></tr>
    <tr><td>Sharpe</td><td>${metrics.sharpe_ratio}</td></tr>
    <tr><td>Max drawdown</td><td>${metrics.max_drawdown_pct}%</td></tr>
    <tr><td>Trades</td><td>${metrics.total_trades}</td></tr>`;

  const positions = await getJSON("/api/positions");
  $("positions-body").innerHTML = positions.map((p) => {
    const pct = p.unrealized_plpc * 100;
    return `<tr><td>${p.symbol}</td><td>${p.qty}</td><td>${fmtUsd(p.avg_entry_price)}</td>
      <td class="${cls(pct)}">${fmtPct(pct)}</td></tr>`;
  }).join("") || `<tr><td colspan="4">Sin posiciones abiertas</td></tr>`;

  const trades = await getJSON("/api/trades");
  const isClose = (side) => side === "SELL" || side === "SELL_STOP";
  $("trades-body").innerHTML = trades.slice().reverse().map((t) => `
    <tr><td>${t.timestamp.slice(0, 16).replace("T", " ")}</td><td>${t.symbol}</td>
      <td>${t.side}</td><td>${fmtUsd(t.price)}</td>
      <td class="${cls(t.pnl)}">${isClose(t.side) ? fmtUsd(t.pnl) : "—"}</td></tr>`).join("")
    || `<tr><td colspan="5">Sin trades todavía</td></tr>`;

  const equity = await getJSON("/api/equity");
  const labels = equity.map((e) => e.date);
  const values = equity.map((e) => e.portfolio_value);
  if (!equityChart) {
    equityChart = new Chart($("equity-chart"), {
      type: "line",
      data: { labels, datasets: [{ data: values, borderColor: "#58a6ff", tension: 0.2, pointRadius: 0 }] },
      options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { color: "#8b949e" } }, y: { ticks: { color: "#8b949e" } } } },
    });
  } else {
    equityChart.data.labels = labels;
    equityChart.data.datasets[0].data = values;
    equityChart.update();
  }
}

$("btn-start").addEventListener("click", async () => {
  await post("/api/start");
  refresh();
});

$("btn-stop").addEventListener("click", async () => {
  const positions = await getJSON("/api/positions");
  let closePositions = false;
  if (positions.length > 0) {
    const yes = confirm(`Tienes ${positions.length} posición(es) abierta(s).\n\nAceptar = cerrar todo y detener.\nCancelar = solo detener (dejar posiciones abiertas).`);
    closePositions = yes;
  }
  await post(`/api/stop?close_positions=${closePositions}`);
  refresh();
});

refresh();
setInterval(refresh, 10000); // polling cada 10s
