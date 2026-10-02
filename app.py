import streamlit as st
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Memorial Técnico de Bombeamento", layout="wide", initial_sidebar_state="collapsed")

g = 9.81

def br(valor, casas=2):
    if valor is None:
        return "—"
    try:
        s = f"{valor:,.{casas}f}"
        s = s.replace(",", "@").replace(".", ",").replace("@", ".")
        return s
    except Exception:
        return str(valor)

def br_signed(valor, casas=2):
    s = br(abs(valor), casas)
    return f"+{s}" if valor >= 0 else f"-{s}"

def parse_br(txt, default=0.0):
    if txt is None:
        return default
    try:
        return float(str(txt).strip().replace(",", "."))
    except (ValueError, TypeError):
        return default

BANCO_FLUIDOS = {
    "Água": {"rho": 998.2, "mu": 0.001002, "pv": 2.34},
    "Óleo SAE 30": {"rho": 860.0, "mu": 0.290, "pv": 0.01},
    "Etanol": {"rho": 789.0, "mu": 0.0012, "pv": 5.95},
    "Glicerina": {"rho": 1260.0, "mu": 1.49, "pv": 0.001},
    "Óleo diesel": {"rho": 830.0, "mu": 0.0035, "pv": 0.30},
    "Gasolina": {"rho": 720.0, "mu": 0.00055, "pv": 35.0},
    "Etilenoglicol 30%": {"rho": 1035.0, "mu": 0.003, "pv": 2.30},
    "Etilenoglicol 35%": {"rho": 1110.0, "mu": 0.0025, "pv": 1.00},
    "Salmoura 10% NaCl": {"rho": 1070.0, "mu": 0.0012, "pv": 2.10},
    "Solução salina genérica": {"rho": 1030.0, "mu": 0.0011, "pv": 2.20},
}

BANCO_MATERIAIS = {
    "Aço comercial (novo)": 0.045,
    "Aço galvanizado": 0.15,
    "Ferro fundido": 0.26,
    "PVC / Plástico liso": 0.0015,
    "Cobre": 0.0015,
}

ACESSORIOS = [
    {"id": "entrada_borda_viva", "nome": "Entrada borda viva", "k": 0.50},
    {"id": "entrada_reentrante", "nome": "Entrada reentrante", "k": 0.78},
    {"id": "entrada_arredondada", "nome": "Entrada arredondada", "k": 0.04},
    {"id": "valvula_pe", "nome": "Válvula de pé c/ crivo", "k": 1.40},
    {"id": "retencao", "nome": "Válvula de retenção", "k": 2.00},
    {"id": "globo", "nome": "Válvula globo", "k": 10.00},
    {"id": "gaveta", "nome": "Válvula gaveta", "k": 0.15},
    {"id": "cotovelo90", "nome": "Cotovelo 90°", "k": 0.90},
    {"id": "cotovelo45", "nome": "Cotovelo 45°", "k": 0.40},
    {"id": "te_direto", "nome": "Tê — escoamento direto", "k": 0.90},
    {"id": "te_ramal", "nome": "Tê — escoamento no ramal", "k": 2.00},
    {"id": "filtro", "nome": "Filtro / strainer limpo", "k": 2.00},
    {"id": "saida", "nome": "Saída p/ reservatório", "k": 1.00},
]

JUSTIFICATIVAS = {
    "bernoulli": {"titulo": "Equação de Bernoulli com bomba e perda de carga", "equacao": "P1/(ρg) + V1²/(2g) + z1 + Hm = P2/(ρg) + V2²/(2g) + z2 + hL", "significado": "Balanço de energia mecânica por unidade de peso. Hm é a energia adicionada pela bomba; hL é a energia dissipada por atrito e singularidades.", "hipoteses": ["Escoamento permanente", "Fluido incompressível", "Regime isotérmico", "Tubulação rígida", "Sem troca de calor relevante"], "origem": "Daniel Bernoulli (1738), estendida para escoamento real.", "referencia": "Fox & McDonald, Cap. 6."},
    "darcy_weisbach": {"titulo": "Perda de carga distribuída (Darcy-Weisbach)", "equacao": "hd = f · (L/D) · V²/(2g)", "significado": "Perda de energia por atrito viscoso ao longo de tubos retos de seção constante.", "hipoteses": ["Tubo reto de seção constante", "Escoamento totalmente desenvolvido", "Rugosidade uniforme"], "origem": "Darcy (1857) e Weisbach (1845).", "referencia": "White, Mecânica dos Fluidos, Cap. 6."},
    "swamee_jain": {"titulo": "Fator de atrito (Swamee-Jain)", "equacao": "f = 0.25 / [log10(ε/(3.7D) + 5.74/Re^0.9)]²", "significado": "Aproximação explícita do Diagrama de Moody para regime turbulento.", "hipoteses": ["Regime turbulento", "Tubo circular", "Rugosidade uniforme"], "origem": "Swamee & Jain (1976), ASCE.", "referencia": "Fox & McDonald, Cap. 8."},
    "perda_localizada": {"titulo": "Perda de carga localizada", "equacao": "hl = Σ K · V²/(2g)", "significado": "Perda de energia em singularidades (válvulas, curvas, entradas, saídas).", "hipoteses": ["Escoamento turbulento desenvolvido", "K tabelado"], "origem": "Crane TP-410, Idelchik.", "referencia": "Crane, Flow of Fluids (TP-410)."},
    "reynolds": {"titulo": "Número de Reynolds", "equacao": "Re = ρVD/μ", "significado": "Razão entre forças inerciais e viscosas. Classifica o regime: laminar (Re<2300), transição, turbulento (Re>4000).", "hipoteses": ["Tubo circular", "Fluido newtoniano"], "origem": "Osborne Reynolds (1883).", "referencia": "Fox & McDonald, Cap. 6."},
    "npsh": {"titulo": "NPSH disponível", "equacao": "NPSHd = (P0 - Pv)/(ρg) + z0 - hL,sucção", "significado": "Energia absoluta disponível na sucção acima da pressão de vapor. NPSHd < NPSHr → cavitação.", "hipoteses": ["Pressões em valores absolutos", "Escoamento sem separação", "Nível constante"], "origem": "Hydraulic Institute (ANSI/HI 9.6.1).", "referencia": "Macintyre, Bombas e Instalações, Cap. 5."},
    "potencia": {"titulo": "Potência de bombeamento", "equacao": "Ph = ρgQHm | Peixo = Ph/ηb | Pelétrica = Peixo/ηm", "significado": "Ph entregue ao fluido; Peixo considera rendimento da bomba; Pelétrica inclui o motor.", "hipoteses": ["Rendimentos constantes", "Motor com FP unitário"], "origem": "Termodinâmica aplicada a máquinas de fluxo.", "referencia": "Macintyre, Cap. 4."},
}

DEFAULTS = {
    "id_projeto": "", "id_responsavel": "", "id_local": "",
    "in_config_sistema": "Reservatórios abertos (mesma pressão)",
    "in_p_atm_local": 101.3,
    "in_P0_abs": 101.3, "in_P2_abs": 101.3,
    "in_fluido": "Água", "in_temp": 20.0,
    "in_Q_m3h": 0.0,
    "in_eta_b": 70, "in_eta_m": 90, "in_NPSHr": 0.0,
    "in_tarifa": 0.0, "in_horas": 0, "in_dias": 0,
    "in_z0": 0.0, "in_z2": 0.0,
    "in_mat_suc": "Aço comercial (novo)", "in_mat_rec": "Aço comercial (novo)",
    "in_D1_mm": 0, "in_L1": 0.0, "in_f1_man": 0.0,
    "in_D2_mm": 0, "in_L2": 0.0, "in_f2_man": 0.0,
    "in_eps_mm": 0.045,
    "in_possui_bocal": False, "in_d3_mm": 0, "in_k_bocal": 0.0,
    "in_ov_rho": False, "in_rho_man": 1000.0,
    "in_ov_mu": False, "in_mu_man": 0.001,
    "in_ov_pv": False, "in_pv_man": 2.34,
    "in_val_manual": 0.0,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

for ac in ACESSORIOS:
    if f"Ks_{ac['id']}" not in st.session_state:
        st.session_state[f"Ks_{ac['id']}"] = 0
    if f"Kr_{ac['id']}" not in st.session_state:
        st.session_state[f"Kr_{ac['id']}"] = 0
    if f"Kval_s_{ac['id']}" not in st.session_state:
        st.session_state[f"Kval_s_{ac['id']}"] = float(ac["k"])
    if f"Kval_r_{ac['id']}" not in st.session_state:
        st.session_state[f"Kval_r_{ac['id']}"] = float(ac["k"])
    if f"Ktxt_s_{ac['id']}" not in st.session_state:
        st.session_state[f"Ktxt_s_{ac['id']}"] = br(ac["k"], 2)
    if f"Ktxt_r_{ac['id']}" not in st.session_state:
        st.session_state[f"Ktxt_r_{ac['id']}"] = br(ac["k"], 2)

def pv_agua(T): return (10 ** (8.07131 - 1730.63 / (233.426 + T))) * 0.133322
def rho_agua(T): return 1000.0 * (1.0 - ((T - 3.98) ** 2 / 508929.0) * ((T + 288.94) / (T + 68.12)))
def mu_agua(T): return 0.001779 / (1.0 + 0.03368 * T + 0.00022099 * T ** 2)

def fator_atrito(Re, eps_m, D_m):
    if Re <= 0 or D_m <= 0: return 0.0
    if Re < 2300: return 64.0 / Re
    arg = (eps_m / (3.7 * D_m)) + (5.74 / (Re ** 0.9))
    return 0.25 / (math.log10(arg) ** 2) if arg > 0 else 0.02

def widget_quantidade(chave):
    if chave not in st.session_state:
        st.session_state[chave] = 0

    def dec():
        st.session_state[chave] = max(0, int(st.session_state[chave]) - 1)

    def inc():
        st.session_state[chave] = int(st.session_state[chave]) + 1

    cm, cv, cp = st.columns([0.28, 0.44, 0.28])
    cm.button("−", key=f"dec_{chave}", on_click=dec, use_container_width=True)
    cv.markdown(
        f"<div style='text-align:center; padding-top:8px; font-size:16px; font-weight:700; color:#1f3a5f;'>{st.session_state[chave]}</div>",
        unsafe_allow_html=True,
    )
    cp.button("+", key=f"inc_{chave}", on_click=inc, use_container_width=True)
    return st.session_state[chave]

st.markdown("""
<div style="border:2px solid #1f3a5f; padding:18px; border-radius:6px; background:#f5f7fa;">
<h1 style="margin:0; color:#1f3a5f; text-align:center; font-size:26px;">MEMORIAL TÉCNICO DE BOMBEAMENTO</h1>
<p style="margin:6px 0 0 0; text-align:center; color:#1f3a5f; font-size:14px;">
Dimensionamento Hidráulico · Perdas de Carga · Altura Manométrica · Potência · NPSH
</p>
<p style="margin:2px 0 0 0; text-align:center; color:#666; font-size:12px;">
CEUNSP — Engenharia de Fluidos
</p>
</div>
""", unsafe_allow_html=True)

st.markdown("## 1. IDENTIFICAÇÃO DO PROJETO")
c1, c2, c3 = st.columns(3)
with c1:
    st.text_input("Título / Descrição do projeto", key="id_projeto", placeholder="Ex: Bombeamento de água quente para lavagem industrial")
with c2:
    st.text_input("Responsável técnico / Grupo", key="id_responsavel", placeholder="Nome do engenheiro ou grupo")
with c3:
    st.text_input("Unidade / Local", key="id_local", placeholder="Ex: Planta industrial — Setor B")

st.divider()

st.markdown("## 2. FLUIDO DE PROCESSO")
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    fluido = st.selectbox("Fluido", list(BANCO_FLUIDOS.keys()), key="in_fluido")
with c2:
    if fluido == "Água":
        temp = st.number_input("Temperatura (°C)", 0.0, 100.0, step=1.0, key="in_temp")
    else:
        temp = 20.0
        st.number_input("Temperatura (°C) — travada", value=20.0, disabled=True)
with c3:
    st.caption("Propriedades calculadas automaticamente.")

if fluido == "Água":
    rho, mu, p_v = rho_agua(temp), mu_agua(temp), pv_agua(temp)
else:
    rho = BANCO_FLUIDOS[fluido]["rho"]
    mu = BANCO_FLUIDOS[fluido]["mu"]
    p_v = BANCO_FLUIDOS[fluido]["pv"]

with st.expander("🔬 Sobrescrever propriedades calculadas"):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.checkbox("Sobrescrever ρ", key="in_ov_rho")
        if st.session_state["in_ov_rho"]:
            rho = st.number_input("ρ (kg/m³)", 1.0, value=float(rho), key="in_rho_man")
    with c2:
        st.checkbox("Sobrescrever μ", key="in_ov_mu")
        if st.session_state["in_ov_mu"]:
            mu = st.number_input("μ (Pa·s)", 1e-7, value=float(mu), format="%.6f", key="in_mu_man")
    with c3:
        st.checkbox("Sobrescrever Pv", key="in_ov_pv")
        if st.session_state["in_ov_pv"]:
            p_v = st.number_input("Pv (kPa abs)", 0.0, value=float(p_v), key="in_pv_man")

st.markdown(f"**Propriedades efetivas:** ρ = `{br(rho, 2)} kg/m³` · μ = `{br(mu, 6)} Pa·s` · Pv = `{br(p_v, 3)} kPa abs`")
st.divider()

st.markdown("## 3. CONDIÇÕES DE OPERAÇÃO")

config_sistema = st.radio(
    "**Configuração do sistema de pressões:**",
    ["Reservatórios abertos (mesma pressão)",
     "Sistema pressurizado (P0 ≠ P2)"],
    key="in_config_sistema",
    horizontal=True,
)

if config_sistema == "Reservatórios abertos (mesma pressão)":
    c_patm, c_esp = st.columns([1, 3])
    with c_patm:
        p_atm_local = st.number_input(
            "Pressão atmosférica local (kPa abs)",
            min_value=0.0, step=0.1,
            key="in_p_atm_local",
            help="Use 101,3 kPa ao nível do mar. Em altitude, reduza conforme tabela.",
        )
    P0_abs = p_atm_local
    P2_abs = p_atm_local
    with c_esp:
        st.info(f"✅ **Aplicado automaticamente:** P0 = P2 = **{br(p_atm_local, 2)} kPa abs**")
else:
    c_p0, c_p2 = st.columns(2)
    with c_p0:
        P0_abs = st.number_input("Pressão na origem P0 (kPa abs)", min_value=0.0, step=0.1, key="in_P0_abs")
    with c_p2:
        P2_abs = st.number_input("Pressão no destino P2 (kPa abs)", min_value=0.0, step=0.1, key="in_P2_abs")
    delta_p = P2_abs - P0_abs
    st.caption(f"ΔP aplicado = **{br_signed(delta_p, 2)} kPa** (carga de pressão = {br_signed(delta_p * 1000.0 / (rho * g), 3)} m)")

st.markdown("---")
c1, c2, c3 = st.columns(3)
with c1:
    Q_m3h = st.number_input("Vazão Q (m³/h)", 0.0, step=0.5, key="in_Q_m3h")
with c2:
    eta_b = st.slider("Rendimento da bomba η_b (%)", 1, 100, key="in_eta_b") / 100
    eta_m = st.slider("Rendimento do motor η_m (%)", 1, 100, key="in_eta_m") / 100
    npshr = st.number_input("NPSH requerido (m)", 0.0, step=0.1, key="in_NPSHr")
with c3:
    tarifa = st.number_input("Tarifa de energia (R$/kWh)", 0.0, step=0.01, key="in_tarifa")
    horas = st.number_input("Horas de operação por dia", 0, 24, key="in_horas")
    dias = st.number_input("Dias de operação por mês", 0, 31, key="in_dias")

st.divider()

st.markdown("## 4. GEOMETRIA DO SISTEMA")
st.caption("💡 Edite o valor de **K** diretamente no campo (aceita vírgula ou ponto). Use **−** e **+** para ajustar a quantidade.")

tab_s, tab_r = st.tabs(["4.1 Linha de Sucção", "4.2 Linha de Recalque"])

with tab_s:
    c1, c2 = st.columns(2)
    with c1:
        z0 = st.number_input("Cota da superfície de sucção z0 (m)", step=0.1, key="in_z0")
        mat_suc = st.selectbox("Material da tubulação", list(BANCO_MATERIAIS.keys()), key="in_mat_suc")
        D1_mm = st.number_input("Diâmetro interno D1 (mm)", 0, step=1, key="in_D1_mm")
        L1 = st.number_input("Comprimento reto L1 (m)", 0.0, key="in_L1")
        f1_man = st.number_input("Fator de atrito f1 (0 = automático)", 0.0, step=0.001, format="%.4f", key="in_f1_man")
    with c2:
        st.markdown("**Singularidades da sucção**")
        hdr = st.columns([0.50, 0.15, 0.35])
        hdr[0].markdown("**Acessório**")
        hdr[1].markdown("**K**")
        hdr[2].markdown("**Quantidade**")
        for ac in ACESSORIOS:
            cc = st.columns([0.50, 0.15, 0.35])
            cc[0].markdown(f"{ac['nome']}")
            k_txt = cc[1].text_input("K", key=f"Ktxt_s_{ac['id']}", label_visibility="collapsed")
            st.session_state[f"Kval_s_{ac['id']}"] = parse_br(k_txt, default=float(ac["k"]))
            with cc[2]:
                widget_quantidade(f"Ks_{ac['id']}")
    sum_k_s = sum(st.session_state[f"Ks_{ac['id']}"] * st.session_state[f"Kval_s_{ac['id']}"] for ac in ACESSORIOS)
    st.info(f"**ΣK da sucção = {br(sum_k_s, 2)}**")

with tab_r:
    c1, c2 = st.columns(2)
    with c1:
        z2 = st.number_input("Cota da superfície de destino z2 (m)", step=0.1, key="in_z2")
        mat_rec = st.selectbox("Material da tubulação ", list(BANCO_MATERIAIS.keys()), key="in_mat_rec")
        D2_mm = st.number_input("Diâmetro interno D2 (mm)", 0, step=1, key="in_D2_mm")
        L2 = st.number_input("Comprimento reto L2 (m)", 0.0, key="in_L2")
        f2_man = st.number_input("Fator de atrito f2 (0 = automático)", 0.0, step=0.001, format="%.4f", key="in_f2_man")
        possui_bocal = st.checkbox("Possui bocal de descarga livre", key="in_possui_bocal")
        if possui_bocal:
            d3_mm = st.number_input("Diâmetro do bocal D3 (mm)", 0, step=1, key="in_d3_mm")
            k_bocal = st.number_input("Coeficiente K do bocal", 0.0, step=0.05, key="in_k_bocal")
        else:
            d3_mm, k_bocal = 0, 0.0
    with c2:
        st.markdown("**Singularidades do recalque**")
        hdr = st.columns([0.50, 0.15, 0.35])
        hdr[0].markdown("**Acessório**")
        hdr[1].markdown("**K**")
        hdr[2].markdown("**Quantidade**")
        for ac in ACESSORIOS:
            cc = st.columns([0.50, 0.15, 0.35])
            cc[0].markdown(f"{ac['nome']}")
            k_txt = cc[1].text_input("K", key=f"Ktxt_r_{ac['id']}", label_visibility="collapsed")
            st.session_state[f"Kval_r_{ac['id']}"] = parse_br(k_txt, default=float(ac["k"]))
            with cc[2]:
                widget_quantidade(f"Kr_{ac['id']}")
    sum_k_r = sum(st.session_state[f"Kr_{ac['id']}"] * st.session_state[f"Kval_r_{ac['id']}"] for ac in ACESSORIOS)
    st.info(f"**ΣK do recalque = {br(sum_k_r, 2)}**")

Q = Q_m3h / 3600.0
D1 = D1_mm / 1000.0
D2 = D2_mm / 1000.0
A1 = math.pi * D1 ** 2 / 4 if D1 > 0 else 0
A2 = math.pi * D2 ** 2 / 4 if D2 > 0 else 0
V1 = Q / A1 if A1 > 0 else 0.0
V2 = Q / A2 if A2 > 0 else 0.0
v1_2g = V1 ** 2 / (2 * g)
v2_2g = V2 ** 2 / (2 * g)
Re1 = rho * V1 * D1 / mu if mu > 0 and D1 > 0 else 0
Re2 = rho * V2 * D2 / mu if mu > 0 and D2 > 0 else 0
rug_s = BANCO_MATERIAIS.get(mat_suc, 0.045) / 1000.0
rug_r = BANCO_MATERIAIS.get(mat_rec, 0.045) / 1000.0
f1 = f1_man if f1_man > 0 else fator_atrito(Re1, rug_s, D1)
f2 = f2_man if f2_man > 0 else fator_atrito(Re2, rug_r, D2)
hL_s = (f1 * (L1 / D1) * v1_2g + sum_k_s * v1_2g) if D1 > 0 else 0.0
v_bocal = Q / (math.pi * (d3_mm / 1000.0) ** 2 / 4) if (possui_bocal and d3_mm > 0) else 0.0
hL_bocal = k_bocal * v_bocal ** 2 / (2 * g) if possui_bocal else 0.0
v_bocal_2g = v_bocal ** 2 / (2 * g) if possui_bocal else 0.0
hL_r = (f2 * (L2 / D2) * v2_2g + sum_k_r * v2_2g + hL_bocal) if D2 > 0 else 0.0
hL_total = hL_s + hL_r
carga_pressao = (P2_abs - P0_abs) * 1000.0 / (rho * g)
delta_z = z2 - z0

if possui_bocal:
    delta_cin = v_bocal_2g - v1_2g
else:
    delta_cin = v2_2g - v1_2g

Hm = delta_z + carga_pressao + delta_cin + hL_total
P_hid = rho * g * Q * Hm / 1000.0
P_eixo = P_hid / eta_b if eta_b > 0 else 0
P_ele = P_eixo / eta_m if eta_m > 0 else 0
consumo = P_ele * horas * dias
custo = consumo * tarifa
NPSHd = (P0_abs - p_v) * 1000.0 / (rho * g) + z0 - hL_s
margem = NPSHd - npshr
razao = NPSHd / npshr if npshr > 0 else 0
regime_s = "Turbulento" if Re1 > 4000 else ("Laminar" if 0 < Re1 < 2300 else ("Transição" if Re1 > 0 else "—"))
regime_r = "Turbulento" if Re2 > 4000 else ("Laminar" if 0 < Re2 < 2300 else ("Transição" if Re2 > 0 else "—"))

if npshr > 0:
    if NPSHd < npshr: status_cav, cor_status = "CRÍTICO", "inverse"
    elif razao < 1.15: status_cav, cor_status = "ALERTA", "off"
    else: status_cav, cor_status = "SEGURO", "normal"
else:
    status_cav, cor_status = "NÃO AVALIADO", "normal"

st.divider()

st.markdown("## 5. RESULTADOS CALCULADOS")

if Q <= 0 or D1 <= 0 or D2 <= 0:
    st.warning("⚠️ Preencha os campos das Seções 3 (vazão) e 4 (diâmetros) para que os resultados sejam calculados.")
else:
    st.markdown("### 5.1 Escoamento e Regime")
    st.markdown(f"""
| Trecho | D (mm) | L (m) | V (m/s) | Re | Regime | f |
|---|---|---|---|---|---|---|
| Sucção | {D1_mm} | {br(L1, 2)} | {br(V1, 4)} | {br(Re1, 0)} | {regime_s} | {br(f1, 5)} |
| Recalque | {D2_mm} | {br(L2, 2)} | {br(V2, 4)} | {br(Re2, 0)} | {regime_r} | {br(f2, 5)} |
""")

    st.markdown("### 5.2 Perdas de Carga")
    st.markdown(f"""
| Componente | Valor (m) |
|---|---|
| Perda distribuída — sucção | {br((f1 * (L1 / D1) * v1_2g) if D1 > 0 else 0, 4)} |
| Perda localizada — sucção (ΣK = {br(sum_k_s, 2)}) | {br(sum_k_s * v1_2g, 4)} |
| **Perda total — sucção** | **{br(hL_s, 4)}** |
| Perda distribuída — recalque | {br((f2 * (L2 / D2) * v2_2g) if D2 > 0 else 0, 4)} |
| Perda localizada — recalque (ΣK = {br(sum_k_r, 2)}) | {br(sum_k_r * v2_2g, 4)} |
| Perda no bocal | {br(hL_bocal, 4)} |
| **Perda total — recalque** | **{br(hL_r, 4)}** |
| **Perda total do sistema (hL)** | **{br(hL_total, 4)}** |
""")

    # ============================================================
    # NOVO: Diagnóstico comparativo de perdas (ideia do app antigo)
    # ============================================================
    if hL_s > 0 and hL_r > 0 and hL_total > 0:
        razao_hl = hL_r / hL_s
        perc_s = hL_s / hL_total * 100
        perc_r = hL_r / hL_total * 100

        if razao_hl > 3:
            texto_diag = (
                f"A linha de **recalque** concentra **{br(perc_r, 1)}%** da perda total "
                f"({br(hL_r, 2)} m), contra apenas **{br(perc_s, 1)}%** na **sucção** "
                f"({br(hL_s, 2)} m). Essa disparidade decorre tipicamente do **maior "
                f"comprimento linear** do recalque ({br(L2, 0)} m contra {br(L1, 0)} m) "
                f"e da **menor seção transversal** (D2 = {D2_mm} mm contra D1 = {D1_mm} mm), "
                f"que elevam a energia cinética e o gradiente de cisalhamento nas paredes do "
                f"duto. Como consequência, qualquer redução adicional no diâmetro ou "
                f"comprimento do recalque terá impacto significativo na altura manométrica total."
            )
        elif razao_hl < 0.33:
            texto_diag = (
                f"A linha de **sucção** concentra **{br(perc_s, 1)}%** da perda total "
                f"({br(hL_s, 2)} m), o que é incomum e pode indicar **subdimensionamento "
                f"da aspiração**. Recomenda-se revisar o diâmetro D1 = {D1_mm} mm e o "
                f"comprimento L1 = {br(L1, 0)} m para reduzir a carga negativa na entrada da bomba."
            )
        else:
            texto_diag = (
                f"As duas linhas apresentam perdas **equilibradas**: sucção {br(perc_s, 1)}% "
                f"({br(hL_s, 2)} m) e recalque {br(perc_r, 1)}% ({br(hL_r, 2)} m). Essa "
                f"distribuição é típica de instalações onde o comprimento e o diâmetro das "
                f"duas linhas são proporcionais."
            )

        st.info(f"**📊 Diagnóstico comparativo de perdas:** {texto_diag}")

    st.markdown("### 5.3 Balanço de Energia (Bernoulli)")
    if possui_bocal:
        cinetica_desc = f"V_bocal²/2g − V1²/2g = {br(v_bocal_2g, 4)} − {br(v1_2g, 4)}"
    else:
        cinetica_desc = f"V2²/2g − V1²/2g = {br(v2_2g, 4)} − {br(v1_2g, 4)}"
    st.markdown(f"""
| Parcela | Valor (m) | Descrição |
|---|---|---|
| Δz | {br_signed(delta_z, 3)} | Desnível geométrico (z2 − z0) |
| Δ(P/ρg) | {br_signed(carga_pressao, 3)} | Diferença de carga de pressão |
| Δ(V²/2g) | {br_signed(delta_cin, 4)} | Energia cinética na descarga ({cinetica_desc}) |
| hL total | {br_signed(hL_total, 4)} | Perda de carga total |
| **Hm** | **{br(Hm, 3)}** | **Altura manométrica requerida** |
""")

    st.markdown("### 5.4 Potência e Energia")
    st.markdown(f"""
| Grandeza | Valor |
|---|---|
| Potência hidráulica (Ph) | {br(P_hid, 3)} kW |
| Potência no eixo (Peixo) — η_b = {br(eta_b*100, 0)}% | {br(P_eixo, 3)} kW |
| Potência elétrica (Pelétrica) — η_m = {br(eta_m*100, 0)}% | {br(P_ele, 3)} kW |
| Consumo mensal | {br(consumo, 1)} kWh |
| Custo mensal | R$ {br(custo, 2)} |
""")

    st.markdown("### 5.5 NPSH e Avaliação de Cavitação")

    # ============================================================
    # NOVO: Aviso destacado quando NPSH não se aplica
    # ============================================================
    if npshr <= 0:
        st.warning(
            "ℹ️ **Análise de NPSH não aplicável** — o NPSH requerido (NPSHr) "
            "não foi informado. Este cenário se enquadra como *sistema em linha "
            "pressurizada* (sem bomba de sucção em tanque atmosférico), onde a "
            "cavitação não se aplica da forma tradicional."
        )

    st.markdown(f"""
| Parcela | Valor |
|---|---|
| (P0 − Pv)/(ρg) | {br((P0_abs - p_v) * 1000.0 / (rho * g), 3)} m |
| z0 | {br(z0, 3)} m |
| − hL,sucção | −{br(hL_s, 4)} m |
| **NPSH disponível (NPSHd)** | **{br(NPSHd, 3)} m** |
| NPSH requerido (NPSHr) | {br(npshr, 3)} m |
| Margem | {br_signed(margem, 3)} m |
| Razão NPSHd / NPSHr | {br(razao, 3)} |
""")

    # ============================================================
    # NOVO: Fator de margem destacado em métricas (ideia do app antigo)
    # ============================================================
    if npshr > 0:
        cm1, cm2, cm3 = st.columns(3)
        cm1.metric("Fator de margem (NPSHd/NPSHr)", f"{br(razao, 2)}",
                   delta="Seguro" if razao >= 1.15 else ("Alerta" if razao >= 1.0 else "Crítico"),
                   delta_color=cor_status)
        cm2.metric("Margem absoluta", f"{br_signed(margem, 2)} m",
                   delta_color=cor_status)
        cm3.metric("Classificação", status_cav)

        if NPSHd < npshr:
            st.error(f"🔴 **CRÍTICO** — Cavitação iminente. NPSHd ({br(NPSHd, 2)} m) < NPSHr ({br(npshr, 2)} m).")
        elif razao < 1.15:
            st.warning(f"🟡 **ALERTA** — Margem baixa ({br(margem, 2)} m). Razão NPSHd/NPSHr = {br(razao, 2)}.")
        else:
            st.success(f"🟢 **SEGURO** — Margem de {br(margem, 2)} m. Razão NPSHd/NPSHr = {br(razao, 2)}.")

st.divider()

st.markdown("## 6. PARECER TÉCNICO")
if Q <= 0 or D1 <= 0 or D2 <= 0:
    st.info("Aguardando preenchimento dos dados de entrada para emitir parecer.")
else:
    if npshr > 0 and NPSHd < npshr:
        par_cav = f"O NPSH disponível ({br(NPSHd, 2)} m) é **inferior** ao NPSH requerido ({br(npshr, 2)} m), caracterizando **risco iminente de cavitação**. Recomenda-se elevar o nível de sucção, reduzir as perdas na linha de aspiração ou substituir a bomba por outra com NPSHr compatível."
    elif npshr > 0 and razao < 1.15:
        par_cav = f"A margem de NPSH ({br(margem, 2)} m) é **inferior a 15%** do NPSH requerido. A operação contínua requer monitoramento; recomenda-se aumentar a margem de segurança."
    elif npshr > 0:
        par_cav = f"O NPSH disponível ({br(NPSHd, 2)} m) supera o requerido ({br(npshr, 2)} m) com margem de {br(margem, 2)} m. A instalação está **livre de cavitação** nas condições atuais."
    else:
        par_cav = "NPSHr não informado — avaliação de cavitação não aplicável."

    if custo > 0:
        par_custo = f"O custo mensal estimado é de R$ {br(custo, 2)}, considerando {horas} h/dia em {dias} dias/mês à tarifa de {br(tarifa, 2)}/kWh."
    else:
        par_custo = "Custos não avaliados (tarifa, horas ou dias não informados)."

    st.markdown(f"""
**Diagnóstico hidráulico.** O sistema opera com vazão de {br(Q_m3h, 2)} m³/h ({br(Q*1000, 3)} L/s). A altura manométrica requerida é de **{br(Hm, 2)} m**, composta por {br(abs(delta_z), 2)} m de desnível, {br(abs(carga_pressao), 2)} m de carga de pressão e **{br(hL_total, 2)} m de perdas**. A bomba deve fornecer {br(P_eixo, 2)} kW no eixo, exigindo {br(P_ele, 2)} kW da rede elétrica.

**Avaliação de cavitação.** {par_cav}

**Observação sobre consumo.** {par_custo}
""")

st.divider()

st.markdown("## APÊNDICE A — CURVAS DO SISTEMA E DA BOMBA")

if Q > 0 and D1 > 0 and D2 > 0:
    Q_op_m3h = Q_m3h
    Q_max = max(Q_op_m3h * 1.6, 10.0)
    Q_vetor_m3h = np.linspace(0.01, Q_max, 60)
    Q_vetor = Q_vetor_m3h / 3600.0
    Hm_sist = []
    for Qv in Q_vetor:
        V1v = Qv / A1 if A1 > 0 else 0
        V2v = Qv / A2 if A2 > 0 else 0
        hL_sv = f1 * (L1 / D1) * (V1v ** 2 / (2 * g)) + sum_k_s * (V1v ** 2 / (2 * g)) if D1 > 0 else 0
        hL_rv = f2 * (L2 / D2) * (V2v ** 2 / (2 * g)) + sum_k_r * (V2v ** 2 / (2 * g)) if D2 > 0 else 0
        vb = Qv / (math.pi * (d3_mm / 1000.0) ** 2 / 4) if (possui_bocal and d3_mm > 0) else 0
        hL_b = k_bocal * vb ** 2 / (2 * g) if possui_bocal else 0
        vb2g = vb ** 2 / (2 * g) if possui_bocal else 0
        if possui_bocal:
            Hm_v = delta_z + carga_pressao + (vb2g - V1v ** 2 / (2 * g)) + hL_sv + hL_rv + hL_b
        else:
            Hm_v = delta_z + carga_pressao + (V2v ** 2 / (2 * g) - V1v ** 2 / (2 * g)) + hL_sv + hL_rv + hL_b
        Hm_sist.append(Hm_v)
    Hm_sist = np.array(Hm_sist)

    st.markdown("**Pontos da curva da bomba** — insira abaixo os pontos do catálogo do fabricante (Q, H):")
    df_default = pd.DataFrame({
        "Q (m³/h)": [0.0, Q_op_m3h * 0.5, Q_op_m3h, Q_op_m3h * 1.3, Q_op_m3h * 1.5],
        "H (m)": [Hm * 1.3, Hm * 1.15, Hm, Hm * 0.85, Hm * 0.7],
    })
    df_bomba = st.data_editor(df_default, num_rows="dynamic", width='stretch', key="df_bomba")
    Q_b = df_bomba["Q (m³/h)"].dropna().values
    H_b = df_bomba["H (m)"].dropna().values
    if len(Q_b) >= 2:
        idx = np.argsort(Q_b)
        Q_b = Q_b[idx]
        H_b = H_b[idx]
        H_bomba_interp = np.interp(Q_vetor_m3h, Q_b, H_b, left=H_b[0], right=H_b[-1])
        diff = Hm_sist - H_bomba_interp
        idx_op = None
        for i in range(len(diff) - 1):
            if diff[i] * diff[i + 1] <= 0:
                idx_op = i
                break
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=Q_vetor_m3h, y=Hm_sist, mode="lines", name="Curva do sistema", line=dict(color="#1f3a5f", width=3)))
        fig.add_trace(go.Scatter(x=Q_b, y=H_b, mode="lines+markers", name="Curva da bomba", line=dict(color="#c0392b", width=3)))
        if idx_op is not None:
            fig.add_trace(go.Scatter(
                x=[Q_vetor_m3h[idx_op]], y=[Hm_sist[idx_op]], mode="markers+text",
                name="Ponto de operação",
                marker=dict(size=16, color="gold", symbol="star", line=dict(color="black", width=2)),
                text=[f"  Q={br(Q_vetor_m3h[idx_op], 1)} m³/h<br>  H={br(Hm_sist[idx_op], 1)} m"],
                textposition="top right",
            ))
        fig.update_layout(
            title="Curva do Sistema × Curva da Bomba",
            xaxis_title="Vazão Q (m³/h)",
            yaxis_title="Altura manométrica H (m)",
            height=500, hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, width='stretch')
        if idx_op is not None:
            st.success(f"🎯 **Ponto de operação:** Q = {br(Q_vetor_m3h[idx_op], 2)} m³/h · H = {br(Hm_sist[idx_op], 2)} m")
    else:
        st.info("Insira pelo menos 2 pontos da bomba para gerar o gráfico.")
else:
    st.info("Preencha os dados de entrada para gerar as curvas.")

st.divider()

st.markdown("## APÊNDICE B — ANÁLISE DE SENSIBILIDADE")
if Q > 0 and D1 > 0:
    c1, c2 = st.columns(2)
    with c1:
        Q_range = st.slider("Variação de Q (±%)", 10, 80, 50, 5)
    with c2:
        D1_range = st.slider("Variação de D1 (±mm)", 5, 50, 20, 5)
    Q_lo = max(0.1, Q_m3h * (1 - Q_range / 100))
    Q_hi = Q_m3h * (1 + Q_range / 100)
    D1_lo = max(10, D1_mm - D1_range)
    D1_hi = D1_mm + D1_range
    Q_arr = np.linspace(Q_lo, Q_hi, 30)
    D1_arr = np.linspace(D1_lo, D1_hi, 30)
    Z = np.zeros((len(D1_arr), len(Q_arr)))
    for i, D1v in enumerate(D1_arr):
        D1m = D1v / 1000.0
        A1v = math.pi * D1m ** 2 / 4
        for j, Qv_m3h in enumerate(Q_arr):
            Qv = Qv_m3h / 3600.0
            V1v = Qv / A1v if A1v > 0 else 0
            Rev = rho * V1v * D1m / mu if mu > 0 else 0
            fv = fator_atrito(Rev, rug_s, D1m)
            hLs_v = fv * (L1 / D1m) * (V1v ** 2 / (2 * g)) + sum_k_s * (V1v ** 2 / (2 * g)) if D1m > 0 else 0
            Z[i, j] = (P0_abs - p_v) * 1000.0 / (rho * g) + z0 - hLs_v
    fig2 = go.Figure(data=go.Heatmap(
        x=Q_arr, y=D1_arr, z=Z, colorscale="RdYlGn",
        colorbar=dict(title="NPSHd (m)"),
        zmid=npshr if npshr > 0 else None,
    ))
    if npshr > 0:
        fig2.add_trace(go.Contour(
            x=Q_arr, y=D1_arr, z=Z,
            contours=dict(showlabels=True, coloring="none"),
            line=dict(width=2, color="black"), showscale=False,
        ))
    fig2.add_trace(go.Scatter(
        x=[Q_m3h], y=[D1_mm], mode="markers+text",
        marker=dict(size=16, color="blue", symbol="x", line=dict(width=3)),
        text=["  Ponto atual"], textposition="top right", showlegend=False,
    ))
    fig2.update_layout(
        title="Mapa de NPSHd × Q × D_sucção",
        xaxis_title="Vazão Q (m³/h)",
        yaxis_title="Diâmetro da sucção D1 (mm)",
        height=500,
    )
    st.plotly_chart(fig2, width='stretch')
else:
    st.info("Preencha os dados de entrada para gerar o mapa de sensibilidade.")

st.divider()

st.markdown("## APÊNDICE C — JUSTIFICATIVAS TÉCNICAS DAS EQUAÇÕES")
st.caption("Fundamentação física, hipóteses e referências bibliográficas.")
for key, j in JUSTIFICATIVAS.items():
    with st.expander(f"📐 {j['titulo']}"):
        st.markdown(f"**Equação:** `{j['equacao']}`")
        st.markdown(f"**Significado físico:** {j['significado']}")
        st.markdown("**Hipóteses adotadas:**")
        for h in j["hipoteses"]:
            st.markdown(f"- {h}")
        st.markdown(f"**Origem histórica:** {j['origem']}")
        st.markdown(f"**Referência:** _{j['referencia']}_")

st.divider()

st.markdown("## APÊNDICE D — VALIDAÇÃO MANUAL")
st.caption("Compare o resultado do aplicativo com o cálculo manual da equipe.")
c1, c2 = st.columns(2)
with c1:
    val_hm = st.number_input("Valor de Hm obtido manualmente (m)", step=0.1, key="in_val_manual")
with c2:
    if val_hm > 0 and Hm != 0:
        erro_abs = abs(val_hm - Hm)
        erro_rel = erro_abs / abs(Hm) * 100
        if erro_rel < 1:
            st.success(f"✅ Concordância excelente — erro de {br(erro_abs, 3)} m ({br(erro_rel, 2)}%)")
        elif erro_rel < 5:
            st.warning(f"⚠️ Concordância aceitável — erro de {br(erro_abs, 3)} m ({br(erro_rel, 2)}%)")
        else:
            st.error(f"❌ Divergência — erro de {br(erro_abs, 3)} m ({br(erro_rel, 2)}%)")
        st.write(f"Aplicativo: **{br(Hm, 3)} m** · Manual: **{br(val_hm, 3)} m**")

st.divider()

st.markdown("## EXPORTAÇÃO DO MEMORIAL")

def linha(label, valor, largura=64):
    pontos = "." * max(2, largura - len(label))
    return f"{label}{pontos}: {valor}"

if npshr > 0:
    if NPSHd < npshr:
        nota_conformidade = (
            "❌ NOTA DE NÃO CONFORMIDADE TÉCNICA:\n"
            "O NPSH disponível é INFERIOR ao NPSH requerido pelo fabricante.\n"
            "RISCO DE CAVITAÇÃO IMINENTE. A operação contínua NÃO é autorizada\n"
            "nas condições atuais. Recomenda-se revisão imediata da linha de\n"
            "sucção (diâmetro, comprimento, singularidades) ou elevação do nível\n"
            "de captação."
        )
        emoji_status = "🔴"
    elif razao < 1.15:
        nota_conformidade = (
            "⚠️ NOTA DE ATENÇÃO OPERACIONAL:\n"
            "A margem de NPSH está ABAIXO de 15% sobre o NPSH requerido.\n"
            "O sistema opera em zona limítrofe. Recomenda-se monitoramento\n"
            "contínuo e avaliação de melhoria na sucção para ampliar a margem\n"
            "de segurança operacional."
        )
        emoji_status = "🟡"
    else:
        nota_conformidade = (
            "✅ NOTA DE CONFORMIDADE TÉCNICA:\n"
            "O escoamento atende aos critérios de NPSH estabelecidos pelo\n"
            "Hydraulic Institute (ANSI/HI 9.6.1). Operação contínua homologada\n"
            "nas condições de projeto declaradas."
        )
        emoji_status = "🟢"
else:
    nota_conformidade = (
        "ℹ️ NPSH requerido não informado pelo fabricante.\n"
        "A avaliação de cavitação não pôde ser realizada."
    )
    emoji_status = "⚪"

config_txt = "Reservatórios abertos à atmosfera" if config_sistema == "Reservatórios abertos (mesma pressão)" else "Sistema pressurizado (P0 ≠ P2)"

if npshr <= 0:
    frase_npsh_final = "não é aplicável (NPSH requerido não informado)"
elif razao >= 1.15:
    frase_npsh_final = "indica condição OPERACIONAL SEGURA"
elif NPSHd >= npshr:
    frase_npsh_final = "exige ATENÇÃO OPERACIONAL por margem limítrofe"
else:
    frase_npsh_final = "indica RISCO CRÍTICO DE CAVITAÇÃO"

# ============================================================
# NOVO: Diagnóstico comparativo de perdas para o relatório
# ============================================================
if hL_s > 0 and hL_r > 0 and hL_total > 0:
    razao_hl = hL_r / hL_s
    perc_s = hL_s / hL_total * 100
    perc_r = hL_r / hL_total * 100

    if razao_hl > 3:
        diag_perdas_txt = (
            f"DIAGNÓSTICO COMPARATIVO TÉCNICO DE PERDAS ESTRUTURAIS:\n"
            f"A linha de recalque concentra {perc_r:.1f}% da perda total ({hL_r:.2f} m),\n"
            f"contra apenas {perc_s:.1f}% na sucção ({hL_s:.2f} m). Essa disparidade\n"
            f"decorre tipicamente do maior comprimento linear do recalque ({L2:.0f} m\n"
            f"contra {L1:.0f} m) e da menor seção transversal (D2 = {D2_mm} mm contra\n"
            f"D1 = {D1_mm} mm), que elevam a energia cinética e o gradiente de\n"
            f"cisalhamento nas paredes do duto. Como consequência, qualquer redução\n"
            f"adicional no diâmetro ou comprimento do recalque terá impacto\n"
            f"significativo na altura manométrica total."
        )
    elif razao_hl < 0.33:
        diag_perdas_txt = (
            f"DIAGNÓSTICO COMPARATIVO TÉCNICO DE PERDAS ESTRUTURAIS:\n"
            f"A linha de sucção concentra {perc_s:.1f}% da perda total ({hL_s:.2f} m),\n"
            f"o que é incomum e pode indicar subdimensionamento da aspiração.\n"
            f"Recomenda-se revisar o diâmetro D1 = {D1_mm} mm e o comprimento\n"
            f"L1 = {L1:.0f} m para reduzir a carga negativa na entrada da bomba."
        )
    else:
        diag_perdas_txt = (
            f"DIAGNÓSTICO COMPARATIVO TÉCNICO DE PERDAS ESTRUTURAIS:\n"
            f"As duas linhas apresentam perdas equilibradas: sucção {perc_s:.1f}%\n"
            f"({hL_s:.2f} m) e recalque {perc_r:.1f}% ({hL_r:.2f} m). Essa distribuição\n"
            f"é típica de instalações onde o comprimento e o diâmetro das duas\n"
            f"linhas são proporcionais."
        )
else:
    diag_perdas_txt = ""

rel = f"""================================================================================
MEMORIAL DESCRITIVO E PARECER DE ENGENHARIA INDUSTRIAL
================================================================================
PROJETO.................: {st.session_state.get('id_projeto', '') or '—'}
RESPONSÁVEL TÉCNICO......: {st.session_state.get('id_responsavel', '') or '—'}
LOCAL / UNIDADE.........: {st.session_state.get('id_local', '') or '—'}
CONFIGURAÇÃO DO SISTEMA.: {config_txt}
FLUIDO DE PROCESSO......: {fluido} a T = {br(temp, 1)} °C
PROPRIEDADES EFETIVAS...: ρ = {br(rho, 2)} kg/m³ | μ = {br(mu, 6)} Pa·s | Pv = {br(p_v, 3)} kPa abs
REGIME OPERACIONAL......: Q = {br(Q*1000, 2)} L/s ({br(Q_m3h, 2)} m³/h)
PRESSÕES................: P0 = {br(P0_abs, 3)} kPa abs | P2 = {br(P2_abs, 3)} kPa abs

================================================================================
1. ANÁLISE QUANTITATIVA DO BALANÇO ENERGÉTICO
================================================================================
{linha("Velocidade média — sucção (V1)", f"{br(V1, 3)} m/s")}
{linha("Velocidade média — recalque (V2)", f"{br(V2, 3)} m/s")}
{linha("Número de Reynolds — sucção", f"{br(Re1, 0)}  →  {regime_s.upper()}")}
{linha("Número de Reynolds — recalque", f"{br(Re2, 0)}  →  {regime_r.upper()}")}
{linha("Fator de atrito — sucção (f1)", f"{br(f1, 5)}")}
{linha("Fator de atrito — recalque (f2)", f"{br(f2, 5)}")}
{linha("ΣK — sucção", f"{br(sum_k_s, 2)}")}
{linha("ΣK — recalque", f"{br(sum_k_r, 2)}")}
{linha("Perda de carga total — sucção", f"{br(hL_s, 4)} m")}
{linha("Perda de carga total — recalque", f"{br(hL_r, 4)} m")}
{linha("Perda de carga total do sistema (hL)", f"{br(hL_total, 4)} m")}
{linha("Desnível geométrico (Δz)", f"{br_signed(delta_z, 3)} m")}
{linha("Carga de pressão Δ(P/ρg)", f"{br_signed(carga_pressao, 3)} m")}
{linha("Variação de energia cinética Δ(V²/2g)", f"{br_signed(delta_cin, 4)} m")}
{linha("ALTURA MANOMÉTRICA TOTAL (Hm)", f"{br(Hm, 3)} m")}

{diag_perdas_txt}

--------------------------------------------------------------------------------
1.1. POTÊNCIA E ENERGIA
--------------------------------------------------------------------------------
{linha("Potência hidráulica transferida ao fluido", f"{br(P_hid, 3)} kW")}
{linha("Potência mecânica no eixo da bomba", f"{br(P_eixo, 3)} kW  (η_b = {br(eta_b*100, 0)}%)")}
{linha("Potência elétrica requerida da rede", f"{br(P_ele, 3)} kW  (η_m = {br(eta_m*100, 0)}%)")}
{linha("Consumo energético mensal projetado", f"{br(consumo, 2)} kWh" if consumo > 0 else "— (não informado)")}
{linha("Faturamento de custo operacional mensal", f"R$ {br(custo, 2)}" if custo > 0 else "— (não informado)")}

================================================================================
2. PARECER DE INTEGRIDADE OPERACIONAL CONTRA CAVITAÇÃO (CRITÉRIO NPSH)
================================================================================
{linha("Pressão absoluta na origem (P0)", f"{br(P0_abs, 3)} kPa abs")}
{linha("Pressão de vapor do fluido (Pv)", f"{br(p_v, 3)} kPa abs")}
{linha("Carga de pressão disponível (P0 − Pv)/(ρg)", f"{br((P0_abs - p_v) * 1000.0 / (rho * g), 3)} m")}
{linha("Cota da superfície de sucção (z0)", f"{br_signed(z0, 3)} m")}
{linha("Perda de carga na sucção (hL,s)", f"−{br(hL_s, 4)} m")}
{linha("NPSH DISPONÍVEL (NPSHd)", f"{br(NPSHd, 3)} m")}
{linha("NPSH REQUERIDO pelo fabricante (NPSHr)", f"{br(npshr, 3)} m")}
{linha("Margem de segurança absoluta", f"{br_signed(margem, 3)} m")}
{linha("Fator de margem (NPSHd / NPSHr)", f"{br(razao, 3)}")}
{linha("Status geral de segurança", f"{emoji_status} {status_cav}")}

{nota_conformidade}

================================================================================
3. CONSIDERAÇÕES FINAIS DE ENGENHARIA
================================================================================
O sistema hidráulico analisado opera com vazão de {br(Q_m3h, 2)} m³/h ({br(Q*1000, 2)} L/s),
requerendo altura manométrica de {br(Hm, 3)} m e potência no eixo de {br(P_eixo, 3)} kW.

As perdas de carga somam {br(hL_total, 3)} m ({br(hL_total/Hm*100 if Hm > 0 else 0, 1)}% da Hm total), das quais
{br(hL_s, 3)} m ocorrem na linha de sucção e {br(hL_r, 3)} m na linha de recalque.

A avaliação de NPSH {frase_npsh_final} nas condições declaradas.

================================================================================
DOCUMENTO GERADO AUTOMATICAMENTE PELA PLATAFORMA CEUNSP - ENGENHARIA DE FLUIDOS
================================================================================
"""

st.text_area("Prévia do memorial técnico", rel, height=560)
st.download_button(
    "📥 Exportar Memorial Técnico (.txt)",
    rel,
    "memorial_tecnico_bombeamento.txt",
    "text/plain",
    width='stretch',
)