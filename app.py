import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Gestión de Movimientos de Personal",
    page_icon="📋",
    layout="wide"
)

# --- CONEXIÓN A GOOGLE SHEETS ---
COLUMNAS_ESPERADAS = [
    "ID", "Fecha", "Solicitante", "Cédula Solicitante", "Cargo Solicitante",
    "Área Origen", "Área Destino", "Tipo de Solicitud", "Personal Afectado",
    "Cédula Afectado", "Cargo Actual", "Cargo Nuevo", "Justificación", "Estado"
]

@st.cache_resource
def conectar_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(creds)
    # Abre la hoja de cálculo por su nombre exacto
    sheet = client.open("BD_Movimientos_Personal").sheet1
    return sheet

def cargar_datos():
    try:
        sheet = conectar_google_sheets()
        registros = sheet.get_all_records()
        # Si la hoja está completamente vacía (sin encabezados), los crea automáticamente
        if not registros and not sheet.row_values(1):
            sheet.append_row(COLUMNAS_ESPERADAS)
            return []
        return registros
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return []

def guardar_nueva_solicitud(nueva_fila_dict):
    sheet = conectar_google_sheets()
    # Si la fila 1 no tiene encabezados, los agregamos primero
    if not sheet.row_values(1):
        sheet.append_row(COLUMNAS_ESPERADAS)
    fila_ordenada = [nueva_fila_dict[col] for col in COLUMNAS_ESPERADAS]
    sheet.append_row(fila_ordenada)

def actualizar_estatus_en_sheets(solicitud_id, nuevo_estado):
    sheet = conectar_google_sheets()
    registros = sheet.get_all_records()
    df = pd.DataFrame(registros)
    if not df.empty and "ID" in df.columns:
        # Buscamos la fila correspondiente al ID (sumamos 2: 1 por índice base 0 y 1 por encabezado)
        indices = df.index[df["ID"] == solicitud_id].tolist()
        if indices:
            fila_sheet = indices[0] + 2
            col_estado = COLUMNAS_ESPERADAS.index("Estado") + 1
            sheet.update_cell(fila_sheet, col_estado, nuevo_estado)

# --- CONFIGURACIÓN DE USUARIOS Y ROLES ---
USUARIOS = {
    "utl_user": {
        "password": "123",
        "nombre": "Coordinador UTL",
        "rol": "solicitante",
        "area_origen": "UTL (Unidad Territorial Local)",
        "areas_permitidas": [
            "Coordinación Operativa y Territorial (UTL)",
            "Talento Humano y Gestión de Personal"
        ]
    },
    "solicitante_general": {
        "password": "123",
        "nombre": "Analista de Área",
        "rol": "solicitante",
        "area_origen": "Formación y Gestión del Conocimiento",
        "areas_permitidas": [
            "Talento Humano y Gestión de Personal",
            "Coordinación Operativa y Territorial (UTL)",
            "Administración, Finanzas y Presupuesto"
        ]
    },
    "resp_th": {
        "password": "admin",
        "nombre": "Responsable Talento Humano",
        "rol": "responsable",
        "area_asignada": "Talento Humano y Gestión de Personal"
    },
    "resp_utl": {
        "password": "admin",
        "nombre": "Responsable Coordinación UTL",
        "rol": "responsable",
        "area_asignada": "Coordinación Operativa y Territorial (UTL)"
    },
    "resp_admin": {
        "password": "admin",
        "nombre": "Responsable Administración y Finanzas",
        "rol": "responsable",
        "area_asignada": "Administración, Finanzas y Presupuesto"
    }
}

TIPOS_SOLICITUD = [
    "Desincorporación",
    "Cese",
    "Cambio de rol o cargo",
    "Sustitución"
]

ESTADOS_POSIBLES = ["Pendiente", "En Revisión", "Aprobado", "Rechazado"]

if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = None

# --- FUNCIÓN DE LOGIN ---
def pantalla_login():
    st.title("🔐 Control de Movimientos de Plantilla")
    st.markdown("Ingrese sus credenciales para acceder al módulo correspondiente a su perfil.")
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            usuario = st.text_input("Usuario").strip()
            clave = st.text_input("Contraseña", type="password").strip()
            btn_login = st.form_submit_button("Iniciar Sesión", use_container_width=True)
            
            if btn_login:
                if usuario in USUARIOS and USUARIOS[usuario]["password"] == clave:
                    st.session_state.usuario_actual = USUARIOS[usuario]
                    st.session_state.usuario_actual["username"] = usuario
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
        
        with st.expander("ℹ️ Credenciales de Prueba"):
            st.markdown("""
            **Usuarios Solicitantes (Solo Formulario):**
            - Usuario: `utl_user` | Contraseña: `123` *(Solo ve áreas vinculadas a UTL)*
            - Usuario: `solicitante_general` | Contraseña: `123` *(Ve las 3 áreas)*
            
            **Responsables de Área (Bandeja + Gráficas):**
            - Talento Humano: `resp_th` | Contraseña: `admin`
            - Coordinación UTL: `resp_utl` | Contraseña: `admin`
            - Administración: `resp_admin` | Contraseña: `admin`
            """)

# --- VISTA 1: SOLICITANTE (SOLO FORMULARIO) ---
def vista_solicitante(datos_usuario):
    st.header("📝 Formulario de Solicitud de Movimiento")
    st.info(f"Conectado como: **{datos_usuario['nombre']}** | Adscripción: **{datos_usuario['area_origen']}**")
    
    with st.form("form_movimiento_personal", clear_on_submit=True):
        st.subheader("1. Datos del Solicitante y Área Destino")
        col1, col2 = st.columns(2)
        
        with col1:
            nombre_solicitante = st.text_input("Nombre y Apellido del Solicitante", value=datos_usuario["nombre"])
            cedula_solicitante = st.text_input("Cédula de Identidad (Solicitante)")
            st.text_input("Área de Origen", value=datos_usuario["area_origen"], disabled=True)
            
        with col2:
            cargo_solicitante = st.text_input("Cargo del Solicitante")
            area_destino = st.selectbox(
                "Área Responsable Destino (Según relación de cargo)", 
                datos_usuario["areas_permitidas"]
            )

        st.markdown("---")
        st.subheader("2. Detalle del Movimiento de Personal")
        
        col3, col4 = st.columns(2)
        with col3:
            tipo_solicitud = st.selectbox("Tipo de Solicitud *", TIPOS_SOLICITUD)
            nombre_afectado = st.text_input("Nombre del Trabajador / Formador Afectado *")
            cedula_afectado = st.text_input("Cédula del Trabajador Afectado *")
            
        with col4:
            cargo_actual = st.text_input("Cargo Actual del Trabajador *")
            cargo_nuevo = st.text_input("Nuevo Cargo / Rol Propuesto (Aplica en Cambio de rol o Sustitución)")
            
        justificacion = st.text_area("Justificación o Motivo Técnico del Movimiento *")
        
        submitted = st.form_submit_button("Enviar Solicitud", use_container_width=True)
        
        if submitted:
            if not nombre_solicitante or not nombre_afectado or not cedula_afectado or not justificacion:
                st.error("⚠️ Por favor complete todos los campos obligatorios marcados con (*).")
            else:
                with st.spinner("Guardando solicitud en Google Sheets..."):
                    registros_actuales = cargar_datos()
                    nuevo_id = max([int(r["ID"]) for r in registros_actuales if str(r.get("ID", "")).isdigit()], default=0) + 1
                    
                    nueva_solicitud = {
                        "ID": nuevo_id,
                        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Solicitante": nombre_solicitante,
                        "Cédula Solicitante": cedula_solicitante,
                        "Cargo Solicitante": cargo_solicitante,
                        "Área Origen": datos_usuario["area_origen"],
                        "Área Destino": area_destino,
                        "Tipo de Solicitud": tipo_solicitud,
                        "Personal Afectado": nombre_afectado,
                        "Cédula Afectado": cedula_afectado,
                        "Cargo Actual": cargo_actual,
                        "Cargo Nuevo": cargo_nuevo if cargo_nuevo else "N/A",
                        "Justificación": justificacion,
                        "Estado": "Pendiente"
                    }
                    guardar_nueva_solicitud(nueva_solicitud)
                st.success(f"✅ ¡Solicitud #{nuevo_id} guardada permanentemente en la base de datos!")

# --- VISTA 2: RESPONSABLE DE ÁREA (BANDEJA Y GRÁFICAS) ---
def vista_responsable(datos_usuario):
    area_resp = datos_usuario["area_asignada"]
    st.header(f"📊 Panel de Control: {area_resp}")
    
    col_top1, col_top2 = st.columns([3, 1])
    with col_top1:
        ver_todas = st.checkbox("Ver solicitudes de todas las áreas (Vista Consolidada)", value=False)
    with col_top2:
        if st.button("🔄 Actualizar Datos", use_container_width=True):
            st.rerun()
            
    registros = cargar_datos()
    
    if not registros:
        st.info("Aún no existen solicitudes registradas en la hoja de Google Sheets.")
        return

    df_total = pd.DataFrame(registros)

    if ver_todas:
        df_area = df_total.copy()
    else:
        df_area = df_total[df_total["Área Destino"] == area_resp].copy()

    if df_area.empty:
        st.warning(f"No hay solicitudes dirigidas a **{area_resp}** en este momento.")
        return

    tab_bandeja, tab_graficas = st.tabs(["📥 Bandeja de Solicitudes y Gestión", "📈 Estadísticas y Gráficas"])

    with tab_bandeja:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_estado = st.selectbox("Filtrar por Estado", ["Todos"] + ESTADOS_POSIBLES)
        with col_f2:
            filtro_tipo = st.selectbox("Filtrar por Tipo de Solicitud", ["Todos"] + TIPOS_SOLICITUD)

        df_filtrado = df_area.copy()
        if filtro_estado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Estado"] == filtro_estado]
        if filtro_tipo != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Tipo de Solicitud"] == filtro_tipo]

        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Actualizar Estatus de Solicitud")
        
        if not df_filtrado.empty:
            col_g1, col_g2, col_g3 = st.columns([1, 1, 1])
            with col_g1:
                sol_id = st.selectbox("ID de Solicitud", df_filtrado["ID"].tolist())
            
            fila_sel = df_total[df_total["ID"] == sol_id]
            if not fila_sel.empty:
                actual_status = fila_sel.iloc[0]["Estado"]
                idx_status = ESTADOS_POSIBLES.index(actual_status) if actual_status in ESTADOS_POSIBLES else 0
                
                with col_g2:
                    nuevo_estado = st.selectbox(
                        "Nuevo Estatus",
                        ESTADOS_POSIBLES,
                        index=idx_status
                    )
                with col_g3:
                    st.write("")
                    st.write("")
                    if st.button("Guardar Cambio de Estatus", use_container_width=True):
                        with st.spinner("Actualizando Google Sheets..."):
                            actualizar_estatus_en_sheets(sol_id, nuevo_estado)
                        st.success(f"Solicitud #{sol_id} actualizada a **{nuevo_estado}**.")
                        st.rerun()

    with tab_graficas:
        st.subheader("Indicadores de Movimientos de Personal")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Solicitudes", len(df_area))
        m2.metric("Pendientes", len(df_area[df_area["Estado"] == "Pendiente"]))
        m3.metric("En Revisión", len(df_area[df_area["Estado"] == "En Revisión"]))
        m4.metric("Aprobadas", len(df_area[df_area["Estado"] == "Aprobado"]))

        st.markdown("---")
        g_col1, g_col2 = st.columns(2)

        with g_col1:
            conteo_tipo = df_area["Tipo de Solicitud"].value_counts().reset_index()
            conteo_tipo.columns = ["Tipo de Solicitud", "Cantidad"]
            
            fig_tipo = px.bar(
                conteo_tipo,
                x="Tipo de Solicitud",
                y="Cantidad",
                color="Tipo de Solicitud",
                title="Distribución por Tipo de Solicitud",
                text_auto=True
            )
            fig_tipo.update_layout(showlegend=False)
            st.plotly_chart(fig_tipo, use_container_width=True)

        with g_col2:
            conteo_estado = df_area["Estado"].value_counts().reset_index()
            conteo_estado.columns = ["Estado", "Cantidad"]
            
            fig_estado = px.pie(
                conteo_estado,
                names="Estado",
                values="Cantidad",
                hole=0.4,
                title="Proporción de Solicitudes por Estado",
                color="Estado",
                color_discrete_map={
                    "Pendiente": "#FFA500",
                    "En Revisión": "#3498DB",
                    "Aprobado": "#2ECC71",
                    "Rechazado": "#E74C3C"
                }
            )
            st.plotly_chart(fig_estado, use_container_width=True)

# --- CONTROLADOR PRINCIPAL ---
if st.session_state.usuario_actual is None:
    pantalla_login()
else:
    user = st.session_state.usuario_actual
    
    with st.sidebar:
        st.markdown(f"### 👤 {user['nombre']}")
        st.caption(f"Rol: **{user['rol'].upper()}**")
        if user["rol"] == "responsable":
            st.caption(f"Área: {user['area_asignada']}")
        else:
            st.caption(f"Origen: {user['area_origen']}")
            
        st.markdown("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.usuario_actual = None
            st.rerun()

    if user["rol"] == "solicitante":
        vista_solicitante(user)
    elif user["rol"] == "responsable":
        vista_responsable(user)
