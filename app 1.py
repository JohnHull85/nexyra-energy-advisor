
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="NEXYRA Energy Advisor", page_icon="⚡️", layout="wide")

# ---------- THEME ----------
PRIMARY = "#00B4B6"   # Electric Teal
SILVER = "#A7A9AC"    # Carbon Silver
BLACK = "#212121"     # Graphite Black
OFFWHITE = "#F7F7F7"  # Off-White

st.markdown(f"""
    <style>
    .small-note {{ color: {BLACK}; opacity: 0.7; font-size: 0.9rem; }}
    .card {{
        background: white;
        border-radius: 12px;
        padding: 16px 18px;
        border: 1px solid {SILVER}22;
        box-shadow: 0 1px 3px rgb(0 0 0 / 6%);
    }}
    h1, h2, h3, h4 {{ color: {BLACK}; }}
    .headerline {{
        border-bottom: 3px solid {PRIMARY};
        margin-top: 0.25rem;
        margin-bottom: 1.5rem;
    }}
    </style>
""", unsafe_allow_html=True)

# ---------- HELPERS ----------
def compute_residential(annual_use_kwh, unit_rate, standing, seg_rate, ev_kwh, hp_kwh,
                        irradiance,
                        sc_bronze, sc_silver, sc_gold,
                        cost_bronze, cost_silver, cost_gold,
                        grid_co2=0.20, export_credit=0.5):
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
        new_bill = post_import * unit_rate + 365 * standing - exported * seg_rate
        savings = baseline_bill - new_bill
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

# ---------- SIDEBAR ----------
st.title("⚡️ NEXYRA Energy Advisor")
st.markdown('<div class="headerline"></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Inputs – Residential")
    annual_use_kwh = st.number_input("Annual electricity use (kWh)", min_value=0, value=4200, step=100)
    unit_rate = st.number_input("Unit rate (£/kWh)", min_value=0.0, value=0.30, step=0.01, format="%.3f")
    standing = st.number_input("Standing charge (£/day)", min_value=0.0, value=0.55, step=0.01, format="%.2f")
    seg_rate = st.number_input("Export (SEG) rate (£/kWh)", min_value=0.0, value=0.15, step=0.01, format="%.2f")
    ev_kwh = st.number_input("EV annual consumption (kWh)", min_value=0, value=0, step=100)
    hp_kwh = st.number_input("Heat pump annual consumption (kWh)", min_value=0, value=0, step=100)
    grid_co2 = st.number_input("Grid carbon intensity (kg CO₂/kWh)", min_value=0.0, value=0.20, step=0.01)

    st.header("Assumptions")
    irradiance = st.number_input("Irradiance (kWh/kWp·yr)", min_value=600, value=1000, step=10)
    sc_bronze = st.slider("Bronze self-consumption rate", 0.4, 0.95, 0.65, step=0.01)
    sc_silver = st.slider("Silver self-consumption rate", 0.4, 0.95, 0.75, step=0.01)
    sc_gold   = st.slider("Gold self-consumption rate",   0.4, 0.95, 0.85, step=0.01)
    export_credit = st.slider("Export CO₂ credit factor", 0.0, 1.0, 0.5, step=0.05)

    st.header("Installed Costs (Residential)")
    cost_bronze = st.number_input("Bronze cost (£)", min_value=0, value=9000, step=500)
    cost_silver = st.number_input("Silver cost (£)", min_value=0, value=13000, step=500)
    cost_gold   = st.number_input("Gold cost (£)", min_value=0, value=18500, step=500)

# ---------- TABS ----------
tab_res, tab_com, tab_comm = st.tabs(["🏠 Residential", "🏢 Commercial", "🏘️ Community"])

with tab_res:
    st.subheader("Residential – Bronze / Silver / Gold")
    df_res, baseline = compute_residential(
        annual_use_kwh, unit_rate, standing, seg_rate, ev_kwh, hp_kwh,
        irradiance, sc_bronze, sc_silver, sc_gold,
        cost_bronze, cost_silver, cost_gold,
        grid_co2, export_credit
    )

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Baseline annual bill", f"£{baseline:,.0f}")
    kpi_cols[1].metric("Bronze bill", f"£{df_res.loc[df_res.Tier=='Bronze','Annual_Bill_GBP'].values[0]:,.0f}")
    kpi_cols[2].metric("Silver bill", f"£{df_res.loc[df_res.Tier=='Silver','Annual_Bill_GBP'].values[0]:,.0f}")
    kpi_cols[3].metric("Gold bill", f"£{df_res.loc[df_res.Tier=='Gold','Annual_Bill_GBP'].values[0]:,.0f}")

    st.markdown("### Results Table")
    st.dataframe(df_res.style.format({
        "PV_kWp": "{:.1f}",
        "Battery_kWh": "{:.1f}",
        "PV_Generation_kWh": "{:,.0f}",
        "Self_Consumed_kWh": "{:,.0f}",
        "Exported_kWh": "{:,.0f}",
        "Post_Import_kWh": "{:,.0f}",
        "Annual_Bill_GBP": "£{:,.0f}",
        "Savings_vs_Baseline_GBP": "£{:,.0f}",
        "Export_Income_GBP": "£{:,.0f}",
        "CO2_Savings_t_per_yr": "{:.2f}",
        "Installed_Cost_GBP": "£{:,.0f}",
        "Simple_Payback_years": "{:.1f}"
    }), use_container_width=True)

    st.markdown("### Charts")
    savings_chart = alt.Chart(df_res).mark_bar(color=PRIMARY).encode(
        x=alt.X("Tier:N", sort=["Bronze","Silver","Gold"]),
        y=alt.Y("Savings_vs_Baseline_GBP:Q", title="Annual Savings (£)")
    ).properties(height=300)
    payback_chart = alt.Chart(df_res).mark_bar(color=SILVER).encode(
        x=alt.X("Tier:N", sort=["Bronze","Silver","Gold"]),
        y=alt.Y("Simple_Payback_years:Q", title="Simple Payback (years)")
    ).properties(height=300)
    c1, c2 = st.columns(2)
    c1.altair_chart(savings_chart, use_container_width=True)
    c2.altair_chart(payback_chart, use_container_width=True)

    st.markdown("### Download")
    csv = df_res.to_csv(index=False).encode("utf-8")
    st.download_button("Download Residential Results (CSV)", data=csv, file_name="nexyra_residential_results.csv", mime="text/csv")

    # Snapshot HTML
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
        <title>NEXYRA – Residential Snapshot</title>
        <style>
            body {{ font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial; color: {BLACK}; }}
            h1 {{ color: {BLACK}; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #e0e0e0; padding: 8px 10px; text-align:center; }}
            th {{ background: {PRIMARY}; color: white; }}
        </style>
        </head><body>
        <h1>NEXYRA – Residential Snapshot</h1>
        <p class="small-note">Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}.</p>
        <table>
            <tr><th>Tier</th><th>Annual Bill (£)</th><th>Savings (£)</th><th>Export Income (£)</th><th>CO₂ Savings (t/yr)</th><th>Installed Cost (£)</th><th>Payback (yrs)</th></tr>
            {table_rows}
        </table>
        </body></html>
        """
        return html

    html_bytes = snapshot_html().encode("utf-8")
    st.download_button("Download Residential Snapshot (HTML)", data=html_bytes, file_name="nexyra_residential_snapshot.html", mime="text/html")
    st.caption("Tip: open the HTML and use your browser's Print → Save as PDF to create a PDF snapshot.")

with tab_com:
    st.subheader("Commercial – Quick Compare")
    c_cols = st.columns(3)
    with c_cols[0]:
        pv_b = st.number_input("Bronze PV (kWp)", value=25, step=5, key="cpvb")
        batt_b = st.number_input("Bronze Battery (kWh)", value=0, step=10, key="cbatb")
        sc_b = st.slider("Bronze Self-consumption", 0.5, 0.95, 0.70, step=0.01, key="cscb")
        cost_b = st.number_input("Bronze Cost (£)", value=30000, step=1000, key="ccostb")
    with c_cols[1]:
        pv_s = st.number_input("Silver PV (kWp)", value=50, step=5, key="cpvs")
        batt_s = st.number_input("Silver Battery (kWh)", value=50, step=10, key="cbats")
        sc_s = st.slider("Silver Self-consumption", 0.5, 0.95, 0.80, step=0.01, key="cscs")
        cost_s = st.number_input("Silver Cost (£)", value=60000, step=1000, key="ccosts")
    with c_cols[2]:
        pv_g = st.number_input("Gold PV (kWp)", value=100, step=5, key="cpvg")
        batt_g = st.number_input("Gold Battery (kWh)", value=100, step=10, key="cbatg")
        sc_g = st.slider("Gold Self-consumption", 0.5, 0.95, 0.85, step=0.01, key="cscg")
        cost_g = st.number_input("Gold Cost (£)", value=130000, step=1000, key="ccostg")

    rows = []
    for tier, pv, batt, sc, cost in [
        ("Bronze", pv_b, batt_b, sc_b, cost_b),
        ("Silver", pv_s, batt_s, sc_s, cost_s),
        ("Gold", pv_g, batt_g, sc_g, cost_g),
    ]:
        r = compute_simple(pv, batt, sc, cost, irradiance, unit_rate, seg_rate)
        r["Tier"] = tier
        rows.append(r)
    df_c = pd.DataFrame(rows)[["Tier"] + [c for c in rows[0].keys() if c != "Tier"]]
    st.dataframe(df_c.style.format({
        "PV_Generation_kWh": "{:,.0f}",
        "Self_Consumed_kWh": "{:,.0f}",
        "Exported_kWh": "{:,.0f}",
        "Bill_Reduction_GBP": "£{:,.0f}",
        "Export_Income_GBP": "£{:,.0f}",
        "Installed_Cost_GBP": "£{:,.0f}",
        "Simple_Payback_years": "{:.1f}"
    }), use_container_width=True)

    st.download_button("Download Commercial Results (CSV)",
                       data=df_c.to_csv(index=False).encode("utf-8"),
                       file_name="nexyra_commercial_results.csv", mime="text/csv")

with tab_comm:
    st.subheader("Community – Quick Compare")
    m_cols = st.columns(3)
    with m_cols[0]:
        pv_b = st.number_input("Bronze PV (kWp)", value=50, step=5, key="mpvb")
        batt_b = st.number_input("Bronze Battery (kWh)", value=20, step=10, key="mbatb")
        sc_b = st.slider("Bronze Self-consumption", 0.5, 0.95, 0.75, step=0.01, key="mscb")
        cost_b = st.number_input("Bronze Cost (£)", value=65000, step=1000, key="mcostb")
    with m_cols[1]:
        pv_s = st.number_input("Silver PV (kWp)", value=100, step=5, key="mpvs")
        batt_s = st.number_input("Silver Battery (kWh)", value=50, step=10, key="mbats")
        sc_s = st.slider("Silver Self-consumption", 0.5, 0.95, 0.82, step=0.01, key="mscs")
        cost_s = st.number_input("Silver Cost (£)", value=120000, step=1000, key="mcosts")
    with m_cols[2]:
        pv_g = st.number_input("Gold PV (kWp)", value=250, step=5, key="mpvg")
        batt_g = st.number_input("Gold Battery (kWh)", value=250, step=10, key="mbatg")
        sc_g = st.slider("Gold Self-consumption", 0.5, 0.95, 0.88, step=0.01, key="mcsg")
        cost_g = st.number_input("Gold Cost (£)", value=320000, step=1000, key="mcostg")

    rows = []
    for tier, pv, batt, sc, cost in [
        ("Bronze", pv_b, batt_b, sc_b, cost_b),
        ("Silver", pv_s, batt_s, sc_s, cost_s),
        ("Gold", pv_g, batt_g, sc_g, cost_g),
    ]:
        r = compute_simple(pv, batt, sc, cost, irradiance, unit_rate, seg_rate)
        r["Tier"] = tier
        rows.append(r)
    df_m = pd.DataFrame(rows)[["Tier"] + [c for c in rows[0].keys() if c != "Tier"]]
    st.dataframe(df_m.style.format({
        "PV_Generation_kWh": "{:,.0f}",
        "Self_Consumed_kWh": "{:,.0f}",
        "Exported_kWh": "{:,.0f}",
        "Bill_Reduction_GBP": "£{:,.0f}",
        "Export_Income_GBP": "£{:,.0f}",
        "Installed_Cost_GBP": "£{:,.0f}",
        "Simple_Payback_years": "{:.1f}"
    }), use_container_width=True)

    st.download_button("Download Community Results (CSV)",
                       data=df_m.to_csv(index=False).encode("utf-8"),
                       file_name="nexyra_community_results.csv", mime="text/csv")

st.markdown("<br><div class='small-note'>© NEXYRA – Intelligent power for modern living.</div>", unsafe_allow_html=True)
