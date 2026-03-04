
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Dashboard DezDez — v12 Estável", layout="wide")
st.title("📊 Dashboard DezDez — Versão V12 Definitiva")

st.sidebar.header("Fonte de dados")
path = st.sidebar.text_input("Caminho do Excel", "ANALISE GERAL.xlsx")


def br_to_float(series):
    if pd.api.types.is_numeric_dtype(series):
        return series

    series = series.astype(str)

    if series.str.contains(",").any():
        return (
            series.str.replace(".", "", regex=False)
                  .str.replace(",", ".", regex=False)
                  .replace(["nan", "None", ""], None)
                  .pipe(pd.to_numeric, errors="coerce")
        )

    return pd.to_numeric(series, errors="coerce")


@st.cache_data
def list_sheets(xlsx_path):
    try:
        return pd.ExcelFile(xlsx_path).sheet_names
    except Exception:
        return []


sheets = list_sheets(path)
sheet = st.sidebar.selectbox("Aba", sheets if sheets else ["FATURAMENTO LOJAS"])


@st.cache_data
def load_raw(xlsx_path, sheet_name):
    df_raw = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None)

    header_metric_row = None
    for i in range(len(df_raw)):
        row_values = df_raw.iloc[i].astype(str).str.lower().tolist()
        if any("r$" in v or "share" in v for v in row_values):
            header_metric_row = i
            break

    header_entity_row = header_metric_row - 1

    entidades = df_raw.iloc[header_entity_row].astype(str).str.strip().tolist()
    metricas = df_raw.iloc[header_metric_row].astype(str).str.strip().tolist()

    multi_cols = list(zip(entidades, metricas))

    df = df_raw.iloc[header_metric_row + 1:].copy()
    df.columns = pd.MultiIndex.from_tuples(multi_cols)
    df = df.loc[:, ~df.columns.duplicated()]
    df = df.dropna(axis=1, how="all")

    return df


@st.cache_data
def reshape(df_multi):

    df = df_multi.copy()

    # Primeira coluna é data (independente do nome)
    date_series = pd.to_datetime(df.iloc[:, 0], errors="coerce")

    df = df.iloc[:, 1:]
    df.index = date_series
    df = df[df.index.notna()]

    entidade_level = 0

    long = df.stack(level=entidade_level).reset_index()

    # Detecta automaticamente coluna datetime
    datetime_col = None
    for col in long.columns:
        if pd.api.types.is_datetime64_any_dtype(long[col]):
            datetime_col = col
            break

    if datetime_col is None:
        # assume primeira coluna é data
        datetime_col = long.columns[0]

    long = long.rename(columns={datetime_col: "Data"})

    entidade_col = long.columns[1]
    long = long.rename(columns={entidade_col: "Entidade"})

    long = long[long["Entidade"].notna()]
    long = long[long["Entidade"].astype(str).str.lower() != "nan"]
    long = long[long["Entidade"].astype(str).str.strip() != ""]

    for col in long.columns:
        if col not in ["Data", "Entidade"]:
            long[col] = br_to_float(long[col])

    long["Mês"] = pd.to_datetime(long["Data"]).dt.to_period("M").astype(str)

    metricas = [c for c in long.columns if c not in ["Data","Entidade","Mês"]]

    return long, metricas


raw = load_raw(path, sheet)
base, available_metrics = reshape(raw)

if base.empty:
    st.error("Base vazia após reshape.")
    st.stop()

meses = sorted(base["Mês"].unique())
entidades = sorted(base["Entidade"].unique())

col1, col2, col3 = st.columns([2,2,3])

with col1:
    meses_sel = st.multiselect("Meses:", meses, default=meses[-3:] if len(meses)>=3 else meses)

with col2:
    ents_sel = st.multiselect("Entidades:", entidades, default=entidades)

with col3:
    metrica = st.selectbox("Métrica:", available_metrics)

df_filtrado = base[base["Mês"].isin(meses_sel) & base["Entidade"].isin(ents_sel)].copy()

ordem_entidades = None

if "LP" in sheet.upper() or "RANK" in sheet.upper():
    mes_recente = sorted(meses_sel)[-1]
    base_recente = df_filtrado[df_filtrado["Mês"] == mes_recente]

    ranking = (
        base_recente.groupby("Entidade", as_index=False)[metrica]
        .mean()
        .sort_values(by=metrica, ascending=False)
        .head(15)
    )

    ordem_entidades = ranking["Entidade"].tolist()
    df_filtrado = df_filtrado[df_filtrado["Entidade"].isin(ordem_entidades)]

df_plot = (
    df_filtrado.groupby(["Entidade","Mês"], as_index=False)[metrica]
    .mean()
)

ordem_meses = sorted(meses_sel, reverse=True)
category_orders = {"Mês": ordem_meses}
if ordem_entidades:
    category_orders["Entidade"] = ordem_entidades

max_val = df_plot[metrica].max()

fig = px.bar(
    df_plot,
    y="Entidade",
    x=metrica,
    color="Mês",
    orientation="h",
    barmode="group",
    category_orders=category_orders
)

fig.update_layout(
    height=800,
    title=f"{sheet} — Comparação Mensal ({metrica})",
    xaxis=dict(range=[0, max_val*1.1], tickformat=",.0f")
)

st.plotly_chart(fig, use_container_width=True)
