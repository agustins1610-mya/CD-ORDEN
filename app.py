import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime
import locale

st.set_page_config(
    page_title="Consejo Directivo — FRO / UNSa",
    page_icon="📋",
    layout="wide"
)

# ── Estilos ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title { text-align:center; color:#5c3d2e; font-size:28px; font-weight:700; margin-bottom:4px; }
    .main-sub   { text-align:center; color:#998; font-size:14px; margin-bottom:24px; }
    .preview-box {
        background:#fff; border:1px solid #d4cfc8; border-radius:8px;
        padding:20px; font-family:Georgia,serif; font-size:13px;
        line-height:1.7; white-space:pre-wrap;
        max-height:500px; overflow-y:auto;
    }
    div[data-testid="stExpander"] { border:1px solid #e8e4df !important; border-radius:8px; }
</style>
""", unsafe_allow_html=True)

# ── Constantes ───────────────────────────────────────────────────────────────
COMISIONES_PRINCIPALES = [
    "Docencia, Disciplina e Investigación",
    "Presupuesto y Hacienda",
    "Interpretación y Reglamento",
    "Docencia e Investigación",
]
COMISIONES_ALL = COMISIONES_PRINCIPALES + [
    "Docencia",
    "Docencia, Disciplina e Inv. y Presupuesto",
    "Hacienda y Presupuesto",
    "Pendiente",
]
MESES_ES = ["enero","febrero","marzo","abril","mayo","junio",
            "julio","agosto","septiembre","octubre","noviembre","diciembre"]

def fecha_es(d):
    if not d:
        return ""
    if isinstance(d, str):
        try:
            d = datetime.strptime(d, "%Y-%m-%d").date()
        except:
            return d
    return f"{d.day} de {MESES_ES[d.month-1]} de {d.year}"

# ── Google Sheets ─────────────────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_NAME = "expedientes_fro"   # nombre de la planilla en Drive
WORKSHEET   = "expedientes"       # nombre de la pestaña

@st.cache_resource
def get_gs_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

def get_worksheet():
    client = get_gs_client()
    sh = client.open(SHEET_NAME)
    return sh.worksheet(WORKSHEET)

@st.cache_data(ttl=30)
def load_expedientes():
    try:
        ws = get_worksheet()
        rows = ws.get_all_records()
        if rows:
            return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"No se pudo conectar con Google Sheets: {e}. Usando datos locales.")
    # Fallback: seed data embebido
    with open("seed_data.json", encoding="utf-8") as f:
        return pd.DataFrame(json.load(f))

def save_expedientes(df):
    try:
        ws = get_worksheet()
        ws.clear()
        ws.update([df.columns.tolist()] + df.fillna("").values.tolist())
        load_expedientes.clear()
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

# ── Inicialización del estado ─────────────────────────────────────────────────
if "df" not in st.session_state:
    st.session_state.df = load_expedientes()

df = st.session_state.df

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">CONSEJO DIRECTIVO — FRO / UNSa</div>', unsafe_allow_html=True)
st.markdown('<div class="main-sub">Gestión de Expedientes y Órdenes del Día</div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📂 Base de Datos", "📋 Orden del Día — Comisión", "🏛️ Orden del Día — Sesión"])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — BASE DE DATOS
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    col_search, col_btn = st.columns([4, 1])
    with col_search:
        busqueda = st.text_input("🔍 Buscar", placeholder="N° expediente, descripción o iniciador...", label_visibility="collapsed")
    with col_btn:
        if st.button("+ Nuevo Expediente", use_container_width=True):
            st.session_state.show_form = not st.session_state.get("show_form", False)

    # Formulario nuevo expediente
    if st.session_state.get("show_form", False):
        with st.container(border=True):
            st.markdown("**Nuevo Expediente**")
            c1, c2, c3 = st.columns(3)
            with c1:
                nuevo_num = st.text_input("N° Expediente *", placeholder="Ej: 123/2026", key="new_num")
            with c2:
                nuevo_ini = st.text_input("Iniciador", placeholder="Nombre completo", key="new_ini")
            with c3:
                nuevo_com = st.selectbox("Comisión", COMISIONES_ALL, key="new_com")
            nuevo_desc = st.text_area("Descripción *", placeholder="Descripción completa del expediente", key="new_desc")
            col_save, col_cancel = st.columns([1, 4])
            with col_save:
                if st.button("💾 Guardar", use_container_width=True):
                    if nuevo_num and nuevo_desc:
                        new_id = int(df["id"].max()) + 1 if len(df) > 0 else 1
                        new_row = pd.DataFrame([{
                            "id": new_id, "numero": nuevo_num,
                            "descripcion": nuevo_desc, "iniciador": nuevo_ini,
                            "comision": nuevo_com,
                            "fecha1": "", "fecha2": "", "fecha3": ""
                        }])
                        st.session_state.df = pd.concat([df, new_row], ignore_index=True)
                        save_expedientes(st.session_state.df)
                        st.session_state.show_form = False
                        st.rerun()
                    else:
                        st.error("N° Expediente y Descripción son obligatorios.")
            with col_cancel:
                if st.button("Cancelar"):
                    st.session_state.show_form = False
                    st.rerun()

    # Filtrar
    df_show = df.copy()
    if busqueda and len(busqueda) >= 2:
        mask = (
            df_show["numero"].str.contains(busqueda, case=False, na=False) |
            df_show["descripcion"].str.contains(busqueda, case=False, na=False) |
            df_show["iniciador"].str.contains(busqueda, case=False, na=False)
        )
        df_show = df_show[mask]

    st.caption(f"{len(df_show)} expedientes")

    # Mostrar tabla con opción de eliminar
    if len(df_show) > 0:
        cols_display = ["numero", "descripcion", "iniciador", "comision", "fecha1"]
        display_df = df_show[cols_display].copy()
        display_df.columns = ["N° Expediente", "Descripción", "Iniciador", "Comisión", "Fecha 1"]
        display_df["Descripción"] = display_df["Descripción"].str[:150] + "..."

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "N° Expediente": st.column_config.TextColumn(width="small"),
                "Descripción": st.column_config.TextColumn(width="large"),
                "Comisión": st.column_config.TextColumn(width="medium"),
                "Fecha 1": st.column_config.TextColumn(width="small"),
            }
        )

        # Eliminar expediente
        with st.expander("🗑️ Eliminar expediente"):
            del_num = st.selectbox(
                "Seleccionar expediente a eliminar",
                options=[""] + df_show["numero"].tolist(),
                format_func=lambda x: x if x else "— elegir —"
            )
            if del_num:
                row = df_show[df_show["numero"] == del_num].iloc[0]
                st.warning(f"**{row['numero']}** — {row['descripcion'][:120]}...")
                if st.button("Confirmar eliminación", type="primary"):
                    st.session_state.df = df[df["numero"] != del_num].reset_index(drop=True)
                    save_expedientes(st.session_state.df)
                    st.success("Eliminado.")
                    st.rerun()

    # Recargar desde Sheets
    if st.button("🔄 Recargar desde Google Sheets"):
        load_expedientes.clear()
        st.session_state.df = load_expedientes()
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — ORDEN DEL DÍA COMISIÓN
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    with st.container(border=True):
        st.markdown("**Configuración de la Reunión**")
        col_f, col_c = st.columns([1, 2])
        with col_f:
            fecha_comision = st.date_input(
                "Fecha de la reunión",
                value=None,
                format="DD/MM/YYYY",
                key="fecha_com"
            )
        with col_c:
            st.markdown("**Comisiones que tratarán:**")
            com_cols = st.columns(2)
            comisiones_sel = []
            for i, c in enumerate(COMISIONES_PRINCIPALES):
                with com_cols[i % 2]:
                    if st.checkbox(c, key=f"com_{i}"):
                        comisiones_sel.append(c)

    # Buscador para agregar expedientes
    st.markdown("**Agregar expedientes al orden del día**")
    busq_com = st.text_input("🔍 Buscar expediente", placeholder="N° expediente, descripción o iniciador...", key="busq_com")

    if busq_com and len(busq_com) >= 2:
        mask = (
            df["numero"].str.contains(busq_com, case=False, na=False) |
            df["descripcion"].str.contains(busq_com, case=False, na=False) |
            df["iniciador"].str.contains(busq_com, case=False, na=False)
        )
        resultados = df[mask].head(15)
        if len(resultados) > 0:
            sel = st.selectbox(
                "Resultados",
                options=[""] + resultados.index.tolist(),
                format_func=lambda x: "" if x == "" else f"Expte. {df.loc[x,'numero']} — {df.loc[x,'descripcion'][:80]}...",
                key="sel_com"
            )
            if sel != "" and st.button("➕ Agregar al orden del día", key="add_com"):
                if "com_items" not in st.session_state:
                    st.session_state.com_items = []
                row = df.loc[sel]
                if not any(i["id"] == row["id"] for i in st.session_state.com_items):
                    st.session_state.com_items.append({
                        "id": row["id"], "numero": row["numero"],
                        "descripcion": row["descripcion"], "obs": ""
                    })
        else:
            st.caption("Sin resultados.")

    # Lista de expedientes seleccionados
    if "com_items" not in st.session_state:
        st.session_state.com_items = []

    if st.session_state.com_items:
        st.markdown(f"**Expedientes seleccionados ({len(st.session_state.com_items)})**")
        items_to_remove = []
        for idx, item in enumerate(st.session_state.com_items):
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.4, 6, 2, 0.5])
                with c1:
                    st.markdown(f"**{idx+1}.**")
                with c2:
                    st.markdown(f"**Expte. N° {item['numero']}**")
                    st.caption(item["descripcion"][:200])
                    item["obs"] = st.text_input(
                        "Observaciones", value=item["obs"],
                        placeholder="Ej: DOCENCIA (opcional)",
                        key=f"obs_com_{idx}", label_visibility="collapsed"
                    )
                with c3:
                    col_u, col_d = st.columns(2)
                    with col_u:
                        if st.button("↑", key=f"up_com_{idx}", disabled=idx == 0):
                            st.session_state.com_items[idx], st.session_state.com_items[idx-1] = \
                                st.session_state.com_items[idx-1], st.session_state.com_items[idx]
                            st.rerun()
                    with col_d:
                        if st.button("↓", key=f"dn_com_{idx}", disabled=idx == len(st.session_state.com_items)-1):
                            st.session_state.com_items[idx], st.session_state.com_items[idx+1] = \
                                st.session_state.com_items[idx+1], st.session_state.com_items[idx]
                            st.rerun()
                with c4:
                    if st.button("✕", key=f"rm_com_{idx}"):
                        items_to_remove.append(idx)
        for i in reversed(items_to_remove):
            st.session_state.com_items.pop(i)
        if items_to_remove:
            st.rerun()

        # Generar texto
        fecha_str = fecha_es(fecha_comision) if fecha_comision else "[FECHA]"
        comisiones_txt = ", ".join(comisiones_sel) if comisiones_sel else "[COMISIONES]"
        texto = f"San Ramón de la Nueva Orán, {fecha_str}.-\n\n"
        texto += "Sres. consejeros:\n\n"
        texto += "Me dirijo a Uds. a fin de invitarlos a la reunión de comisiones del Consejo Directivo "
        texto += "de la Facultad Regional Orán de la Universidad Nacional de Salta, que se llevará a cabo "
        texto += "el día [DÍA Y HORA] en forma Presencial en la sala de reuniones, "
        texto += "a fin de tratar los siguientes Temas:\n\n"
        texto += f"Comisiones de {comisiones_txt}:\n\n"
        for i, item in enumerate(st.session_state.com_items):
            texto += f"{i+1}. Expte. N° {item['numero']}. {item['descripcion']}"
            if item["obs"]:
                texto += f" - {item['obs']}"
            texto += "\n\n"
        texto += "Los saludo atentamente.-"

        st.markdown("**Vista previa**")
        st.code(texto, language=None)
        st.download_button(
            "⬇️ Descargar como .txt",
            data=texto.encode("utf-8"),
            file_name=f"orden_comision_{fecha_comision or 'sin_fecha'}.txt",
            mime="text/plain"
        )
        if st.button("🗑️ Limpiar lista"):
            st.session_state.com_items = []
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — ORDEN DEL DÍA SESIÓN
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    with st.container(border=True):
        st.markdown("**Configuración de la Sesión**")
        cs1, cs2, cs3 = st.columns(3)
        with cs1:
            nro_sesion = st.text_input("N° Sesión", placeholder="Ej: 01/2026", key="nro_ses")
        with cs2:
            fecha_sesion = st.date_input("Fecha", value=None, format="DD/MM/YYYY", key="fecha_ses")
        with cs3:
            tipo_sesion = st.selectbox("Tipo", ["Ordinaria", "Extraordinaria"], key="tipo_ses")

    # Actas
    with st.expander("📄 Actas", expanded=True):
        if "actas_list" not in st.session_state:
            st.session_state.actas_list = [""]
        actas_to_remove = []
        for i, acta in enumerate(st.session_state.actas_list):
            c1, c2 = st.columns([10, 1])
            with c1:
                st.session_state.actas_list[i] = st.text_input(
                    f"Acta {i+1}", value=acta,
                    placeholder="Ej: ACTA N°19/09-12-2025-ORDINARIA N°14",
                    key=f"acta_{i}", label_visibility="collapsed"
                )
            with c2:
                if st.button("✕", key=f"rm_acta_{i}"):
                    actas_to_remove.append(i)
        for i in reversed(actas_to_remove):
            st.session_state.actas_list.pop(i)
        if st.button("+ Agregar Acta"):
            st.session_state.actas_list.append("")
            st.rerun()

    # Sección activa
    seccion_activa = st.radio(
        "Agregar expediente a:",
        ["ASUNTOS ENTRADOS", "INFORMES DE COMISIÓN"],
        horizontal=True, key="sec_ses"
    )
    sec_key = "ses_entrados" if seccion_activa == "ASUNTOS ENTRADOS" else "ses_informes"

    busq_ses = st.text_input("🔍 Buscar expediente", placeholder="N° expediente, descripción o iniciador...", key="busq_ses")
    if busq_ses and len(busq_ses) >= 2:
        mask = (
            df["numero"].str.contains(busq_ses, case=False, na=False) |
            df["descripcion"].str.contains(busq_ses, case=False, na=False) |
            df["iniciador"].str.contains(busq_ses, case=False, na=False)
        )
        resultados_s = df[mask].head(15)
        if len(resultados_s) > 0:
            sel_s = st.selectbox(
                "Resultados",
                options=[""] + resultados_s.index.tolist(),
                format_func=lambda x: "" if x == "" else f"Expte. {df.loc[x,'numero']} — {df.loc[x,'descripcion'][:80]}...",
                key="sel_ses"
            )
            if sel_s != "" and st.button("➕ Agregar", key="add_ses"):
                if sec_key not in st.session_state:
                    st.session_state[sec_key] = []
                row = df.loc[sel_s]
                if not any(i["id"] == row["id"] for i in st.session_state[sec_key]):
                    st.session_state[sec_key].append({
                        "id": row["id"], "numero": row["numero"],
                        "descripcion": row["descripcion"],
                        "despacho": "", "extra": ""
                    })
        else:
            st.caption("Sin resultados.")

    for sk, label in [("ses_entrados", "ASUNTOS ENTRADOS"), ("ses_informes", "INFORMES DE COMISIÓN")]:
        if sk not in st.session_state:
            st.session_state[sk] = []
        items = st.session_state[sk]
        if items:
            st.markdown(f"**{label} ({len(items)})**")
            to_remove = []
            for idx, item in enumerate(items):
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([0.4, 6, 2, 0.5])
                    with c1:
                        st.markdown(f"**{idx+1}.**")
                    with c2:
                        st.markdown(f"**Expte. N° {item['numero']}**")
                        st.caption(item["descripcion"][:180])
                        if sk == "ses_informes":
                            item["despacho"] = st.text_input(
                                "Despacho", value=item["despacho"],
                                placeholder="Ej: Despacho N° 1 de la Comisión de...",
                                key=f"des_{sk}_{idx}", label_visibility="collapsed"
                            )
                        item["extra"] = st.text_input(
                            "Texto adicional", value=item["extra"],
                            placeholder="Observaciones adicionales (opcional)",
                            key=f"ext_{sk}_{idx}", label_visibility="collapsed"
                        )
                    with c3:
                        cu, cd = st.columns(2)
                        with cu:
                            if st.button("↑", key=f"up_{sk}_{idx}", disabled=idx == 0):
                                items[idx], items[idx-1] = items[idx-1], items[idx]
                                st.rerun()
                        with cd:
                            if st.button("↓", key=f"dn_{sk}_{idx}", disabled=idx == len(items)-1):
                                items[idx], items[idx+1] = items[idx+1], items[idx]
                                st.rerun()
                    with c4:
                        if st.button("✕", key=f"rm_{sk}_{idx}"):
                            to_remove.append(idx)
            for i in reversed(to_remove):
                items.pop(i)
            if to_remove:
                st.rerun()

    # Generar texto sesión
    entrados = st.session_state.get("ses_entrados", [])
    informes = st.session_state.get("ses_informes", [])
    if entrados or informes:
        fecha_str = fecha_es(fecha_sesion) if fecha_sesion else "[FECHA]"
        texto_s = f"San Ramón de la Nueva Orán, {fecha_str}.-\n\n"
        texto_s += "Sres. consejeros:\n\n"
        texto_s += (f"Me dirijo a Uds. a fin de invitarlos a la Sesión {tipo_sesion} "
                    f"N° {nro_sesion or '[N°]'} del Consejo Directivo de la Facultad Regional Orán "
                    f"de la Universidad Nacional de Salta, que se llevará a cabo el día [DÍA] "
                    f"a partir de horas [HORA] en forma Presencial en la sala de reuniones, "
                    f"a fin de tratar los siguientes Temas:\n\n")
        gn = 1
        texto_s += f"{gn}. ACTAS:\n"
        gn += 1
        for i, a in enumerate([a for a in st.session_state.get("actas_list", []) if a.strip()]):
            texto_s += f"   {i+1}. {a}\n"
        texto_s += f"\n{gn}. ASUNTOS SOBRE TABLA:\n\n"
        gn += 1
        texto_s += f"{gn}. INFORME DE DIRECCIÓN:\n\n"
        gn += 1
        texto_s += f"{gn}. ASUNTOS ENTRADOS:\n"
        gn += 1
        for i, item in enumerate(entrados):
            texto_s += f"   {i+1}. Expte. N° {item['numero']}. {item['descripcion']}"
            if item["extra"]:
                texto_s += f" {item['extra']}"
            texto_s += "\n"
        texto_s += f"\n{gn}. INFORMES DE COMISIÓN:\n"
        for i, item in enumerate(informes):
            texto_s += f"   {i+1}. Expte. N° {item['numero']}. {item['descripcion']}"
            if item["despacho"]:
                texto_s += f"\n      {item['despacho']}"
            if item["extra"]:
                texto_s += f"\n      {item['extra']}"
            texto_s += "\n"
        texto_s += "\nSolicito confirme recepción, los saludo atentamente.-"

        st.markdown("**Vista previa**")
        st.code(texto_s, language=None)
        st.download_button(
            "⬇️ Descargar como .txt",
            data=texto_s.encode("utf-8"),
            file_name=f"orden_sesion_{nro_sesion or 'sin_numero'}_{fecha_sesion or 'sin_fecha'}.txt",
            mime="text/plain"
        )
        if st.button("🗑️ Limpiar sesión"):
            st.session_state.ses_entrados = []
            st.session_state.ses_informes = []
            st.session_state.actas_list = [""]
            st.rerun()
