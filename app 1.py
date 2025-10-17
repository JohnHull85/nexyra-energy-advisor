import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime

st.set_page_config(page_title="NEXYRA Energy Advisor", page_icon="⚡️", layout="wide")

# ---------- BRAND ----------
PRIMARY = "#00B4B6"   # Electric Teal
SILVER  = "#A7A9AC"   # Carbon Silver
BLACK   = "#212121"   # Graphite Black

st.markdown(f"""
<style>
.small-note {{ color:{BLACK}; opacity:0.75; font-size:0.9rem; }}
.headerline {{ border-bottom: 3px solid {PRIMARY}; margin: 0.25rem 0 1rem 0; }}
.card {{ background: white; border:1px solid {SILVER}33; border-radius:12px; padding:16px; }}
.help {{ color:{BLACK}; opacity:0.7; font-size:0.85rem; }}
</style>
""", unsafe_allow_html=True)

# ---------- HELPERS ----------
REGION_IRRADIANCE = {
    "South (1050)": 1050,
    "Midlands (950)": 950,
    "North (900)": 900,
    "Custom": None,
}

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def compute_residential(annual_use_kwh, unit_rate, standing, seg_rate,
                        ev_kwh, hp_kwh,
                        irradiance,
                        sc_bronze, sc_silver, sc_gold,
                        cost_bronze, cost_silver, cost_gold,
                        grid_co2=0.20, export_credit=0.5):
    """Return DataFrame of Bronze/Silver/Gold results for residential scenario."""
    presets = [
        ("Bronze", 3.6, 5.0, sc_bronze, cost_bronze, False, False),
        ("Silver", 4.0, 9.5, sc_silver, cost_silver, True,  False),
        ("Gold",   6.0, 13.0, sc_gold,  cost_gold,  True,  True),
    ]
    rows = []
    baseline_bill = (annual_use_kwh + ev_kwh + hp_kwh) * unit_rate + 365 * standing
    for tier, pv_kwp, batt_kwh, sc_rate, cost, has_ev, has_ems in presets:
        pv_gen = pv_kwp * irradiance
        self_used = pv_gen * sc_rate
        exported = max(pv_gen - self_used, 0)
        post_import = max((annual_use_kwh + ev_kwh + hp_kwh) - self_used, 0)
        new_bill = max(post_import * unit_rate + 365 * standing - exported * seg_rate, 0)  # clamp >=0
        savings = max(baseline_bill - new_bill, 0)  # clamp >=0
        export_income = exported * seg_rate
        co2_t = (self_used * grid_co2 + exported * grid_co2 * export_credit) / 1000.0
        payback = (cost / savings) if savings > 0 else np.nan
        rows.append(dict(
            Tier=tier,
            PV_kWp=pv_kwp,
            Battery_kWh=batt_kwh,
            PV_Generation_kWh=pv_gen,
            Self_Consumed_kWh=self_used,
            Exported_kWh=exported,
            Post_Import_kWh=post_import,
            Annual_Bill_GBP=new_bill,
            Savings_vs_Baseline_GBP=savings,
            Export_Income_GBP=export_income,
            CO2_Savings_t_per_yr=co2_t,
            Installed_Cost_GBP=cost,
            Simple_Payback_years=payback
        ))
    df = pd.DataFrame(rows)
    return df, baseline_bill

def compute_simple(pv_kwp, battery_kwh, sc_rate, installed_cost, irradiance, unit_rate, seg_rate):
    pv_gen = pv_kwp * irradiance
    self_used = pv_gen * sc_rate
    exported = max(pv_gen - self_used, 0)
    bill_reduction = self_used * unit_rate
    export_income = exported * seg_rate
    annual_benefit = bill_reduction + export_income
    payback = installed_cost / annual_benefit if annual_benefit > 0 else np.nan
    return dict(
        PV_Generation_kWh=pv_gen,
        Self_Consumed_kWh=self_used,
        Exported_kWh=exported,
        Bill_Reduction_GBP=bill_reduction,
        Export_Income_GBP=export_income,
        Installed_Cost_GBP=installed_cost,
        Simple_Payback_years=payback
    )

# ---------- UI ----------
st.title("⚡️ NEXYRA Energy Advisor")
st.markdown('<div class="headerline"></div>', unsafe_allow_html=True)

mode = st.toggle("Advanced mode", value=False, help="Toggle to reveal detailed assumptions and editable tier costs.")

# --- LEFT: SIMPLE INPUTS ---
left, right = st.columns([1,1])

with left:
    st.subheader("Basics")
    annual_use_kwh = st.number_input("Annual electricity use (kWh)", min_value=0, value=4200, step=100, help="Total household consumption in the last 12 months.")
    unit_rate = st.number_input("Unit rate (£/kWh)", min_value=0.00, max_value=1.00, value=0.30, step=0.01, format="%.3f", help="Blended rate inc. VAT. Typical UK 0.20–0.40.")
    standing = st.number_input("Standing charge (£/day)", min_value=0.00, max_value=2.00, value=0.55, step=0.01, format="%.2f", help="Daily fixed charge from your supplier.")
    seg_rate  = st.number_input("Export (SEG) rate (£/kWh)", min_value=0.00, max_value=0.50, value=0.15, step=0.01, format="%.2f", help="Your supplier's Smart Export Guarantee rate.")

with right:
    st.subheader("Appliances")
    # EV helper
    ev_use_mode = st.radio("EV input", ["No EV", "kWh per year", "Miles per year"], index=0, horizontal=True,
                           help="Choose how to enter EV usage. Miles convert to kWh using 0.30 kWh/mile by default.")
    if ev_use_mode == "No EV":
        ev_kwh = 0
    elif ev_use_mode == "kWh per year":
        ev_kwh = st.number_input("EV annual consumption (kWh)", min_value=0, value=0, step=100)
    else:
        miles = st.number_input("EV miles per year", min_value=0, value=0, step=1000)
        wh_per_mile = st.number_input("EV energy per mile (kWh/mile)", min_value=0.10, max_value=0.60, value=0.30, step=0.01)
        ev_kwh = int(miles * wh_per_mile)

    # Heat pump
    hp_has = st.checkbox("Heat pump in home?", value=False)
    hp_kwh = st.number_input("Heat pump annual consumption (kWh)", min_value=0, value=0, step=200, disabled=not hp_has)

st.markdown("---")

# --- ADVANCED ---
if mode:
    st.subheader("Advanced assumptions & costs")
    a1, a2, a3 = st.columns([1,1,1])
    with a1:
        region = st.selectbox("Region irradiance preset", list(REGION_IRRADIANCE.keys()), index=1,
                              help="Irradiance ≈ annual kWh produced by 1 kWp of PV. Choose a region or 'Custom'.")
        if REGION_IRRADIANCE[region] is None:
            irradiance = st.number_input("Custom irradiance (kWh/kWp·yr)", min_value=700, max_value=1200, value=1000, step=10)
        else:
            irradiance = REGION_IRRADIANCE[region]

        grid_co2 = st.number_input("Grid carbon intensity (kg CO₂/kWh)", min_value=0.0, max_value=1.0, value=0.20, step=0.01,
                                   help="DEFRA 2024-25 typical ~0.20 kg/kWh.")

    with a2:
        st.markdown("**Self-consumption rates**")
        sc_bronze = st.slider("Bronze", 0.40, 0.95, 0.65, step=0.01, help="Share of PV directly used on-site.")
        sc_silver = st.slider("Silver", 0.40, 0.95, 0.75, step=0.01)
        sc_gold   = st.slider("Gold",   0.40, 0.95, 0.85, step=0.01)
        export_credit = st.slider("Export CO₂ credit factor", 0.0, 1.0, 0.5, step=0.05,
                                  help="How much exported kWh displaces grid CO₂. 0.5 = 50% credited.")

    with a3:
        st.markdown("**Installed cost per tier (editable)**")
        cost_bronze = st.number_input("Bronze cost (£)", min_value=0, value=9000, step=250)
        cost_silver = st.number_input("Silver cost (£)", min_value=0, value=13000, step=250)
        cost_gold   = st.number_input("Gold cost (£)", min_value=0, value=18500, step=250)
else:
    # Simple defaults (hidden in simple mode)
    irradiance = 1000
    sc_bronze, sc_silver, sc_gold = 0.65, 0.75, 0.85
    export_credit = 0.5
    grid_co2 = 0.20
    cost_bronze, cost_silver, cost_gold = 9000, 13000, 18500

# ---------- CALC ----------
df_res, baseline = compute_residential(
    annual_use_kwh=annual_use_kwh,
    unit_rate=unit_rate,
    standing=standing,
    seg_rate=seg_rate,
    ev_kwh=ev_kwh,
    hp_kwh=hp_kwh,
    irradiance=irradiance,
    sc_bronze=sc_bronze, sc_silver=sc_silver, sc_gold=sc_gold,
    cost_bronze=cost_bronze, cost_silver=cost_silver, cost_gold=cost_gold,
    grid_co2=grid_co2, export_credit=export_credit
)

# ---------- OUTPUT ----------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Baseline annual bill", f"£{baseline:,.0f}")
k2.metric("Bronze bill", f"£{df_res.loc[df_res.Tier=='Bronze','Annual_Bill_GBP'].values[0]:,.0f}")
k3.metric("Silver bill", f"£{df_res.loc[df_res.Tier=='Silver','Annual_Bill_GBP'].values[0]:,.0f}")
k4.metric("Gold bill", f"£{df_res.loc[df_res.Tier=='Gold','Annual_Bill_GBP'].values[0]:,.0f}")

st.markdown("### Results")
st.dataframe(df_res.style.format({
    "PV_kWp": "{:.1f}",
    "Battery_kWh": "{:.1f}",
    "PV_Generation_kWh": "{:,.0f}",
    "Self_Consumed_kWh": "{:,.0f}",
    "Exported_KWh": "{:,.0f}",
    "Post_Import_kWh": "{:,.0f}",
    "Annual_Bill_GBP": "£{:,.0f}",
    "Savings_vs_Baseline_GBP": "£{:,.0f}",
    "Export_Income_GBP": "£{:,.0f}",
    "CO2_Savings_t_per_yr": "{:.2f}",
    "Installed_Cost_GBP": "£{:,.0f}",
    "Simple_Payback_years": "{:.1f}"
}), use_container_width=True)

st.markdown("### Charts")
chart1 = alt.Chart(df_res).mark_bar(color=PRIMARY).encode(
    x=alt.X("Tier:N", sort=["Bronze","Silver","Gold"]),
    y=alt.Y("Savings_vs_Baseline_GBP:Q", title="Annual Savings (£)")
).properties(height=300)
chart2 = alt.Chart(df_res).mark_bar(color=SILVER).encode(
    x=alt.X("Tier:N", sort=["Bronze","Silver","Gold"]),
    y=alt.Y("Simple_Payback_years:Q", title="Simple Payback (years)")
).properties(height=300)
c1, c2 = st.columns(2)
c1.altair_chart(chart1, use_container_width=True)
c2.altair_chart(chart2, use_container_width=True)

st.markdown("### Download")
csv = df_res.to_csv(index=False).encode("utf-8")
st.download_button("Download Results (CSV)", data=csv, file_name="nexyra_residential_results.csv", mime="text/csv")

def snapshot_html():
    rows = []
    for _, r in df_res.iterrows():
        rows.append(f"""
            <tr>
              <td>{r['Tier']}</td>
              <td>£{r['Annual_Bill_GBP']:,.0f}</td>
              <td>£{r['Savings_vs_Baseline_GBP']:,.0f}</td>
              <td>£{r['Export_Income_GBP']:,.0f}</td>
              <td>{r['CO2_Savings_t_per_yr']:.2f} t</td>
              <td>£{r['Installed_Cost_GBP']:,.0f}</td>
              <td>{r['Simple_Payback_years']:.1f}</td>
            </tr>
        """)
    table_rows = "\n".join(rows)
    html = f"""
    <html><head>
    <meta charset="utf-8">
    <title>NEXYRA – Snapshot</title>
    <style>
        body {{ font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial; color: {BLACK}; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #e0e0e0; padding: 8px 10px; text-align:center; }}
        th {{ background: {PRIMARY}; color: white; }}
        h1 {{ margin: 0; padding: 0.5rem 0; }}
        .note {{ color: #666; font-size: 0.9rem; }}
    </style>
    </head><body>
    <h1>NEXYRA – Residential Snapshot</h1>
    <p class="note">Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} · Assumptions set in the app.</p>
    <table>
        <tr><th>Tier</th><th>Annual Bill (£)</th><th>Savings (£)</th><th>Export Income (£)</th><th>CO₂ Savings (t/yr)</th><th>Installed Cost (£)</th><th>Payback (yrs)</th></tr>
        {table_rows}
    </table>
    </body></html>
    """
    return html

html_bytes = snapshot_html().encode("utf-8")
st.download_button("Download Snapshot (HTML)", data=html_bytes, file_name="nexyra_snapshot.html", mime="text/html")
st.caption("Tip: open the HTML and use your browser's Print → Save as PDF.")

st.markdown("<br><div class='small-note'>© NEXYRA – Intelligent power for modern living.</div>", unsafe_allow_html=True)