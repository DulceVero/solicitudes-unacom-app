import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
import re
from google.oauth2.service_account import Credentials
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Gestión de Movimientos de Personal",
    page_icon="📋",
    layout="wide"
)

# --- ESTILO CSS PARA ENCABEZADOS DE TABLAS (AZUL CLARO Y NEGRITA) ---
st.markdown("""
<style>
    /* Estilo para encabezados de st.dataframe y st.data_editor */
    [data-testid="stDataFrame"] th,
    [data-testid="stDataEditor"] th,
    .stDataFrame thead tr th {
        background-color: #D6EAF8 !important;
        color: #1B4F72 !important;
        font-weight: 800 !important;
        border-bottom: 2px solid #85C1E9 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- LISTAS MAESTRAS ---
ESTADOS_VENEZUELA = [
    "Amazonas", "Anzoátegui", "Apure", "Aragua", "Barinas", "Bolívar",
    "Carabobo", "Cojedes", "Delta Amacuro", "Distrito Capital", "Falcón",
    "Guárico", "La Guaira", "Lara", "Mérida", "Miranda", "Monagas",
    "Nueva Esparta", "Portuguesa", "Sucre", "Táchira", "Trujillo",
    "Yaracuy", "Zulia"
]

TIPOS_SOLICITUD = [
    "Sustitución",
    "Incorporación",
    "Desincorporación",
    "Cambio de rol"
]

MOTIVOS_SUSTITUCION = ["Renuncia", "Cambio de rol", "Cese"]
MOTIVOS_DESINCORPORACION = ["Renuncia", "Cese", "Otro"]
ROLES_CAMBIO = ["Formador", "PNF", "UTL"]

GRADOS_INSTRUCCION = [
    "Bachiller",
    "Técnico Medio",
    "Técnico Superior Universitario (TSU)",
    "Licenciado / Ingeniero / Profesional Universitario",
    "Especialización",
    "Maestría",
    "Doctorado"
]

STATUS_SOLICITUD = ["Pendiente", "En Revisión", "Aprobado", "Rechazado"]

# Columnas unificadas en Google Sheets (23 columnas exactas con 'Status')
COLUMNAS_ESPERADAS = [
    "ID", "Fecha", "Solicitante", "Cédula Solicitante",
    "Tipo Solicitante", "Área de Trabajo", "Nombre de Comuna", "Código SITUR",
    "Tipo de Solicitud", "Estado Geográfico",
    "Saliente Nombre", "Saliente Apellido", "Saliente Cédula",
    "Motivo", "Detalle Motivo",
    "Entrante Nombre", "Entrante Apellido", "Entrante Cédula",
    "Profesión", "Grado Instrucción", "Entrante Correo",
    "Nuevo Rol", "Status"
]

# Columnas específicas para cada vista administrativa (siempre incluyen 'Status')
COLUMNAS_UTL_PNF = [
    "ID", "Fecha", "Status", "Tipo de Solicitud", "Estado Geográfico",
    "Solicitante", "Cédula Solicitante", "Área de Trabajo",
    "Saliente Nombre", "Saliente Apellido", "Saliente Cédula",
    "Motivo", "Detalle Motivo",
    "Entrante Nombre", "Entrante Apellido", "Entrante Cédula",
    "Profesión", "Grado Instrucción", "Entrante Correo", "Nuevo Rol"
]

COLUMNAS_FORMADOR = [
    "ID", "Fecha", "Status", "Tipo de Solicitud", "Estado Geográfico",
    "Solicitante", "Cédula Solicitante", "Nombre de Comuna", "Código SITUR",
    "Saliente Nombre", "Saliente Apellido", "Saliente Cédula",
    "Motivo", "Detalle Motivo",
    "Entrante Nombre", "Entrante Apellido", "Entrante Cédula",
    "Profesión", "Grado Instrucción", "Entrante Correo", "Nuevo Rol"
]

COLUMNAS_CONSOLIDADO = [
    "ID", "Fecha", "Status", "Tipo Solicitante", "Tipo de Solicitud", "Estado Geográfico",
    "Solicitante", "Cédula Solicitante", "Área de Trabajo", "Nombre de Comuna", "Código SITUR",
    "Saliente Nombre", "Saliente Apellido", "Saliente Cédula",
    "Motivo", "Detalle Motivo",
    "Entrante Nombre", "Entrante Apellido", "Entrante Cédula",
    "Profesión", "Grado Instrucción", "Entrante Correo", "Nuevo Rol"
]

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_google_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open("BD_Movimientos_Personal").sheet1
    return sheet

def reparar_o_inicializar_hoja(sheet):
    """Asegura que la fila 1 tenga exactamente los 23 encabezados con 'Status'."""
    fila_1 = sheet.row_values(1)
    if not fila_1 or fila_1 != COLUMNAS_ESPERADAS:
        sheet.update("A1", [COLUMNAS_ESPERADAS])

def cargar_datos():
    try:
        sheet = conectar_google_sheets()
        reparar_o_inicializar_hoja(sheet)
        registros = sheet.get_all_records(expected_headers=COLUMNAS_ESPERADAS)
        
        if registros:
            df = pd.DataFrame(registros)
            for col in COLUMNAS_ESPERADAS:
                if col not in df.columns:
                    df[col] = "Pendiente" if col == "Status" else "N/A"
            # Normalizar valores vacíos en Status
            df["Status"] = df["Status"].replace(["", "N/A", None], "Pendiente").fillna("Pendiente")
            df = df[COLUMNAS_ESPERADAS]
            return df.to_dict(orient="records")
        return []
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return []

def guardar_nueva_solicitud(nueva_fila_dict):
    sheet = conectar_google_sheets()
    reparar_o_inicializar_hoja(sheet)
    fila_ordenada = [str(nueva_fila_dict.get(col, "N/A")) for col in COLUMNAS_ESPERADAS]
    sheet.append_row(fila_ordenada)

def actualizar_multiples_status_en_sheets(cambios_dict):
    """Actualiza en bloque todos los Status modificados en la tabla."""
    sheet = conectar_google_sheets()
    reparar_o_inicializar_hoja(sheet)
    registros = sheet.get_all_records(expected_headers=COLUMNAS_ESPERADAS)
    df = pd.DataFrame(registros)
    if not df.empty and "ID" in df.columns:
        col_status = COLUMNAS_ESPERADAS.index("Status") + 1
        for sol_id, nuevo_status in cambios_dict.items():
            indices = df.index[df["ID"].astype(str) == str(sol_id)].tolist()
            if indices:
                fila_sheet = indices[0] + 2
                sheet.update_cell(fila_sheet, col_status, nuevo_status)

def es_correo_valido(correo):
    patron = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(patron, correo.strip()))

# --- CONFIGURACIÓN DE USUARIOS Y ROLES ---
USUARIOS = {
    "utl_user": {
        "password": "123",
        "nombre": "Usuario UTL",
        "rol": "solicitante",
        "subtipo": "UTL"
    },
    "pnf_user": {
        "password": "123",
        "nombre": "Usuario PNF",
        "rol": "solicitante",
        "subtipo": "PNF"
    },
    "formador_user": {
        "password": "123",
        "nombre": "Usuario Formador",
        "rol": "solicitante",
        "subtipo": "Formador"
    },
    "admin_utl": {
        "password": "admin",
        "nombre": "Administrador UTL",
        "rol": "responsable",
        "area_asignada": "UTL"
    },
    "admin_formador": {
        "password": "admin",
        "nombre": "Administrador Formador",
        "rol": "responsable",
        "area_asignada": "Formador"
    },
    "admin_pnf": {
        "password": "admin",
        "nombre": "Administrador PNF",
        "rol": "responsable",
        "area_asignada": "PNF"
    },
    "admin_general": {
        "password": "admin",
        "nombre": "Coordinación General (Consolidado)",
        "rol": "consolidado",
        "area_asignada": "Todas las Áreas"
    }
}

if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = None

# --- FUNCIÓN AUXILIAR PARA CAMPOS DE SOLICITANTE SEGÚN PERFIL ---
def renderizar_datos_solicitante(datos_usuario):
    st.markdown("#### Datos del Solicitante y Ubicación")
    subtipo = datos_usuario.get("subtipo", "UTL")
    area_trabajo = "N/A"
    nombre_comuna = "N/A"
    codigo_situr = "N/A"

    c_g1, c_g2 = st.columns(2)
    with c_g1:
        estado_vzla = st.selectbox("Estado *", ESTADOS_VENEZUELA)
        nombre_solicitante = st.text_input("Nombre y Apellido del Solicitante *", value=datos_usuario["nombre"])
    with c_g2:
        cedula_solicitante = st.number_input("Cédula del Solicitante (Solo números) *", min_value=0, step=1, format="%d")
        if subtipo in ["UTL", "PNF"]:
            area_trabajo = st.text_input("Área de Trabajo *", placeholder="Escriba su área de trabajo")
        else:
            nombre_comuna = st.text_input("Nombre de Comuna *", placeholder="Indique el nombre de la comuna")

    if subtipo == "Formador":
        codigo_situr = st.text_input("Código SITUR *", placeholder="Ingrese el código SITUR")

    return estado_vzla, nombre_solicitante, cedula_solicitante, area_trabajo, nombre_comuna, codigo_situr

def validar_datos_ubicacion(subtipo, area_trabajo, nombre_comuna, codigo_situr):
    if subtipo in ["UTL", "PNF"]:
        return bool(area_trabajo and area_trabajo.strip() and area_trabajo != "N/A")
    else:
        return bool(
            nombre_comuna and nombre_comuna.strip() and nombre_comuna != "N/A" and
            codigo_situr and codigo_situr.strip() and codigo_situr != "N/A"
        )

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
            - UTL: `utl_user` | Contraseña: `123`
            - PNF: `pnf_user` | Contraseña: `123`
            - Formador: `formador_user` | Contraseña: `123`

            **Administradores por Área:**
            - Admin UTL: `admin_utl` | Contraseña: `admin`
            - Admin Formador: `admin_formador` | Contraseña: `admin`
            - Admin PNF: `admin_pnf` | Contraseña: `admin`

            **Vista Consolidada General (Todas las áreas):**
            - Admin General: `admin_general` | Contraseña: `admin`
            """)

# --- VISTA 1: SOLICITANTE (FORMULARIO DINÁMICO) ---
def vista_solicitante(datos_usuario):
    subtipo = datos_usuario.get("subtipo", "UTL")
    st.header("📝 Solicitud de Movimiento de Personal")
    st.info(f"Conectado como: **{datos_usuario['nombre']}** | Perfil: **{subtipo}**")

    st.subheader("1. Seleccione el Tipo de Solicitud")
    tipo_solicitud = st.radio(
        "¿Qué movimiento de plantilla desea tramitar?",
        TIPOS_SOLICITUD,
        horizontal=True
    )

    st.markdown("---")

    # ==========================================
    # FORMULARIO 1: SUSTITUCIÓN
    # ==========================================
    if tipo_solicitud == "Sustitución":
        st.subheader("📋 Formulario de Sustitución")

        col_m1, col_m2 = st.columns([1, 2])
        with col_m1:
            motivo_sust = st.selectbox("Motivo de la sustitución *", MOTIVOS_SUSTITUCION)
        with col_m2:
            if motivo_sust == "Cese":
                razon_cese = st.text_input("Especifique la razón del cese *", placeholder="Indique
