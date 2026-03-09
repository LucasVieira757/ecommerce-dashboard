import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px

# ======================
# CONFIG
# ======================
st.set_page_config(
    page_title="Dashboard E-commerce",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard E-commerce")
st.caption("Análise interativa de vendas, clientes e pedidos")

DB_URL = "postgresql://postgres.rkgifmejnvzquqafjyhk:Monteazul!23@aws-1-us-east-2.pooler.supabase.com:5432/postgres"
engine = create_engine(DB_URL)


# ======================
# CACHE DA BASE
# ======================
@st.cache_data
def carregar_base():
    query = """
    SELECT
        p.id_pedido,
        p.data_pedido,
        p.status_pedido,
        p.forma_pagamento,
        p.valor_total,
        c.cidade,
        c.estado,
        i.valor_item,
        pr.nome_produto
    FROM fato_pedidos p
    JOIN dim_clientes c
        ON p.id_cliente = c.id_cliente
    JOIN fato_itens_pedido i
        ON p.id_pedido = i.id_pedido
    JOIN dim_produtos pr
        ON i.id_produto = pr.id_produto
    """
    df = pd.read_sql(query, engine)
    df["data_pedido"] = pd.to_datetime(df["data_pedido"])
    return df


df = carregar_base()

# ======================
# SESSION STATE
# ======================
defaults = {
    "filtro_estado": "Todos",
    "filtro_cidade": "Todas",
    "filtro_status": "Todos",
    "filtro_produto": "Todos",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "periodo" not in st.session_state:
    st.session_state["periodo"] = (
        df["data_pedido"].min().date(),
        df["data_pedido"].max().date()
    )

# ======================
# SIDEBAR
# ======================
st.sidebar.header("Filtros")

if st.sidebar.button("Limpar seleções"):
    st.session_state["filtro_estado"] = "Todos"
    st.session_state["filtro_cidade"] = "Todas"
    st.session_state["filtro_status"] = "Todos"
    st.session_state["filtro_produto"] = "Todos"
    st.session_state["periodo"] = (
        df["data_pedido"].min().date(),
        df["data_pedido"].max().date()
    )
    st.rerun()

estados = ["Todos"] + sorted(df["estado"].dropna().unique().tolist())
cidades = ["Todas"] + sorted(df["cidade"].dropna().unique().tolist())
status_lista = ["Todos"] + sorted(df["status_pedido"].dropna().unique().tolist())
produtos = ["Todos"] + sorted(df["nome_produto"].dropna().unique().tolist())

filtro_estado = st.sidebar.selectbox(
    "Estado",
    estados,
    index=estados.index(st.session_state["filtro_estado"]) if st.session_state["filtro_estado"] in estados else 0
)

filtro_cidade = st.sidebar.selectbox(
    "Cidade",
    cidades,
    index=cidades.index(st.session_state["filtro_cidade"]) if st.session_state["filtro_cidade"] in cidades else 0
)

filtro_status = st.sidebar.selectbox(
    "Status do pedido",
    status_lista,
    index=status_lista.index(st.session_state["filtro_status"]) if st.session_state["filtro_status"] in status_lista else 0
)

filtro_produto = st.sidebar.selectbox(
    "Produto",
    produtos,
    index=produtos.index(st.session_state["filtro_produto"]) if st.session_state["filtro_produto"] in produtos else 0
)

periodo = st.sidebar.date_input(
    "Período",
    value=st.session_state["periodo"],
    min_value=df["data_pedido"].min().date(),
    max_value=df["data_pedido"].max().date()
)

if len(periodo) == 2:
    data_inicio, data_fim = periodo
    st.session_state["periodo"] = (data_inicio, data_fim)
else:
    data_inicio, data_fim = st.session_state["periodo"]

# sincroniza sidebar -> session_state
st.session_state["filtro_estado"] = filtro_estado
st.session_state["filtro_cidade"] = filtro_cidade
st.session_state["filtro_status"] = filtro_status
st.session_state["filtro_produto"] = filtro_produto

# ======================
# FILTROS NA BASE
# ======================
df_filtrado = df.copy()

df_filtrado = df_filtrado[
    (df_filtrado["data_pedido"].dt.date >= data_inicio) &
    (df_filtrado["data_pedido"].dt.date <= data_fim)
]

if filtro_estado != "Todos":
    df_filtrado = df_filtrado[df_filtrado["estado"] == filtro_estado]

if filtro_cidade != "Todas":
    df_filtrado = df_filtrado[df_filtrado["cidade"] == filtro_cidade]

if filtro_status != "Todos":
    df_filtrado = df_filtrado[df_filtrado["status_pedido"] == filtro_status]

if filtro_produto != "Todos":
    df_filtrado = df_filtrado[df_filtrado["nome_produto"] == filtro_produto]

if df_filtrado.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

# remove duplicidade de pedido para KPI
df_pedidos = df_filtrado.drop_duplicates(subset=["id_pedido"]).copy()
df_entregues = df_pedidos[df_pedidos["status_pedido"] == "Entregue"].copy()

# ======================
# KPIs
# ======================
st.subheader("Visão Executiva")

receita_total = df_entregues["valor_total"].sum()
ticket_medio = df_entregues["valor_total"].mean()
total_pedidos = df_pedidos["id_pedido"].nunique()
taxa_cancelamento = df_pedidos["status_pedido"].eq("Cancelado").mean() * 100

receita_total = 0 if pd.isna(receita_total) else receita_total
ticket_medio = 0 if pd.isna(ticket_medio) else ticket_medio
total_pedidos = 0 if pd.isna(total_pedidos) else total_pedidos
taxa_cancelamento = 0 if pd.isna(taxa_cancelamento) else taxa_cancelamento

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total pedidos", f"{int(total_pedidos):,}".replace(",", "."))
k2.metric("Receita total", f"R$ {receita_total:,.2f}")
k3.metric("Ticket médio", f"R$ {ticket_medio:,.2f}")
k4.metric("Taxa cancelamento", f"{taxa_cancelamento:.2f}%")

st.markdown("---")

# ======================
# AGREGAÇÕES
# ======================
df_mes = (
    df_entregues
    .assign(mes=df_entregues["data_pedido"].dt.to_period("M").astype(str))
    .groupby("mes", as_index=False)["valor_total"]
    .sum()
    .rename(columns={"valor_total": "faturamento"})
)

df_status = (
    df_pedidos
    .groupby("status_pedido", as_index=False)["id_pedido"]
    .count()
    .rename(columns={"id_pedido": "total"})
)

df_cidade = (
    df_entregues
    .groupby("cidade", as_index=False)["valor_total"]
    .sum()
    .sort_values("valor_total", ascending=False)
    .head(10)
    .rename(columns={"valor_total": "faturamento"})
)

df_estado = (
    df_entregues
    .groupby("estado", as_index=False)["valor_total"]
    .sum()
    .sort_values("valor_total", ascending=False)
    .rename(columns={"valor_total": "faturamento"})
)

df_produtos = (
    df_filtrado[df_filtrado["status_pedido"] == "Entregue"]
    .groupby("nome_produto", as_index=False)["valor_item"]
    .sum()
    .sort_values("valor_item", ascending=False)
    .head(10)
    .rename(columns={"valor_item": "faturamento"})
)

# ======================
# GRÁFICOS
# ======================
c1, c2 = st.columns(2)

with c1:
    if not df_mes.empty:
        fig1 = px.line(
            df_mes,
            x="mes",
            y="faturamento",
            markers=True,
            title="Faturamento por mês"
        )
        fig1.update_traces(textposition="top center")
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("Sem dados de faturamento.")

with c2:
    if not df_status.empty:
        fig2 = px.bar(
            df_status,
            x="status_pedido",
            y="total",
            text="total",
            title="Pedidos por status"
        )
        fig2.update_traces(textposition="outside")
        sel_status = st.plotly_chart(
            fig2,
            use_container_width=True,
            key="chart_status",
            on_select="rerun",
            selection_mode="points",
        )

        pontos = sel_status.get("selection", {}).get("points", []) if isinstance(sel_status, dict) else []
        if pontos:
            idx = pontos[0]["point_index"]
            escolhido = df_status.iloc[idx]["status_pedido"]
            if st.session_state["filtro_status"] != escolhido:
                st.session_state["filtro_status"] = escolhido
                st.rerun()
    else:
        st.info("Sem dados de status.")

c3, c4 = st.columns(2)

with c3:
    if not df_cidade.empty:
        fig3 = px.bar(
            df_cidade,
            x="cidade",
            y="faturamento",
            text="faturamento",
            title="Top cidades por faturamento"
        )
        fig3.update_traces(texttemplate="R$ %{y:,.0f}", textposition="outside")
        sel_cidade = st.plotly_chart(
            fig3,
            use_container_width=True,
            key="chart_cidade",
            on_select="rerun",
            selection_mode="points",
        )

        pontos = sel_cidade.get("selection", {}).get("points", []) if isinstance(sel_cidade, dict) else []
        if pontos:
            idx = pontos[0]["point_index"]
            escolhida = df_cidade.iloc[idx]["cidade"]
            if st.session_state["filtro_cidade"] != escolhida:
                st.session_state["filtro_cidade"] = escolhida
                st.rerun()
    else:
        st.info("Sem dados de cidade.")

with c4:
    if not df_estado.empty:
        fig4 = px.bar(
            df_estado,
            x="estado",
            y="faturamento",
            text="faturamento",
            title="Faturamento por estado"
        )
        fig4.update_traces(texttemplate="R$ %{y:,.0f}", textposition="outside")
        sel_estado = st.plotly_chart(
            fig4,
            use_container_width=True,
            key="chart_estado",
            on_select="rerun",
            selection_mode="points",
        )

        pontos = sel_estado.get("selection", {}).get("points", []) if isinstance(sel_estado, dict) else []
        if pontos:
            idx = pontos[0]["point_index"]
            escolhido = df_estado.iloc[idx]["estado"]
            if st.session_state["filtro_estado"] != escolhido:
                st.session_state["filtro_estado"] = escolhido
                st.rerun()
    else:
        st.info("Sem dados de estado.")

if not df_produtos.empty:
    fig5 = px.bar(
        df_produtos,
        x="nome_produto",
        y="faturamento",
        text="faturamento",
        title="Top produtos por faturamento"
    )
    fig5.update_traces(texttemplate="R$ %{y:,.0f}", textposition="outside")
    sel_prod = st.plotly_chart(
        fig5,
        use_container_width=True,
        key="chart_produto",
        on_select="rerun",
        selection_mode="points",
    )

    pontos = sel_prod.get("selection", {}).get("points", []) if isinstance(sel_prod, dict) else []
    if pontos:
        idx = pontos[0]["point_index"]
        escolhido = df_produtos.iloc[idx]["nome_produto"]
        if st.session_state["filtro_produto"] != escolhido:
            st.session_state["filtro_produto"] = escolhido
            st.rerun()
else:
    st.info("Sem dados de produtos.")

with st.expander("Detalhes dos pedidos"):
    st.dataframe(
        df_pedidos[
            ["id_pedido", "data_pedido", "status_pedido", "cidade", "estado", "forma_pagamento", "valor_total"]
        ].sort_values(["data_pedido", "id_pedido"], ascending=[False, False]),
        use_container_width=True
    )