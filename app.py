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

ESTADOS_SOLICITUD = ["Pendiente", "En Revisión", "Aprobado", "Rechazado"]

# Columnas unificadas para Google Sheets
COLUMNAS_ESPERADAS = [
    "ID", "Fecha", "Solicitante", "Cédula Solicitante",
    "Tipo Solicitante", "Área de Trabajo", "Nombre de Comuna", "Código SITUR",
    "Tipo de Solicitud", "Estado Geográfico",
    "Saliente Nombre", "Saliente Apellido", "Saliente Cédula",
    "Motivo", "Detalle Motivo",
    "Entrante Nombre", "Entrante Apellido", "Entrante Cédula",
    "Profesión", "Grado Instrucción", "Entrante Correo",
    "Nuevo Rol", "Estado"
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

def cargar_datos():
    try:
        sheet = conectar_google_sheets()
        registros = sheet.get_all_records()
        if not registros and not sheet.row_values(1):
            sheet.append_row(COLUMNAS_ESPERADAS)
            return []
        return registros
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return []

def guardar_nueva_solicitud(nueva_fila_dict):
    sheet = conectar_google_sheets()
    encabezados_actuales = sheet.row_values(1)
    if not encabezados_actuales:
        sheet.append_row(COLUMNAS_ESPERADAS)
    elif encabezados_actuales != COLUMNAS_ESPERADAS:
        sheet.update("A1", [COLUMNAS_ESPERADAS])
        
    fila_ordenada = [nueva_fila_dict.get(col, "N/A") for col in COLUMNAS_ESPERADAS]
    sheet.append_row(fila_ordenada)

def actualizar_estatus_en_sheets(solicitud_id, nuevo_estado):
    sheet = conectar_google_sheets()
    registros = sheet.get_all_records()
    df = pd.DataFrame(registros)
    if not df.empty and "ID" in df.columns:
        indices = df.index[df["ID"] == solicitud_id].tolist()
        if indices:
            fila_sheet = indices[0] + 2
            col_estado = COLUMNAS_ESPERADAS.index("Estado") + 1
            sheet.update_cell(fila_sheet, col_estado, nuevo_estado)

# --- CONFIGURACIÓN DE USUARIOS Y ROLES ---
USUARIOS = {
    # Solicitantes
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
    # Administradores / Responsables por Área
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
    # Administrador General (Consolidado)
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
    
    # Inicialización segura de variables para evitar UnboundLocalError
    area_trabajo = "N/A"
    nombre_comuna = "N/A"
    codigo_situr = "N/A"
    
    c_g1, c_g2 = st.columns(2)
    with c_g1:
        estado_vzla = st.selectbox("Estado *", ESTADOS_VENEZUELA)
        nombre_solicitante = st.text_input("Nombre y Apellido del Solicitante *", value=datos_usuario["nombre"])
    with c_g2:
        cedula_solicitante = st.text_input("Cédula del Solicitante *", placeholder="Ej. V-12345678")
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
                razon_cese = st.text_input("Especifique la razón del cese *", placeholder="Indique el motivo detallado del cese...")
            else:
                razon_cese = "N/A"
                st.write("")
                st.caption("Si selecciona 'Cese', se habilitará un campo para detallar la razón.")

        with st.form("form_sustitucion", clear_on_submit=True):
            estado_vzla, nombre_solicitante, cedula_solicitante, area_trabajo, nombre_comuna, codigo_situr = renderizar_datos_solicitante(datos_usuario)

            st.markdown("---")
            st.markdown("#### 👤 Datos del Personal Saliente")
            c_sal1, c_sal2, c_sal3 = st.columns(3)
            with c_sal1:
                sal_nombre = st.text_input("Nombre (Saliente) *")
            with c_sal2:
                sal_apellido = st.text_input("Apellido (Saliente) *")
            with c_sal3:
                sal_cedula = st.text_input("Cédula (Saliente) *")

            st.markdown("---")
            st.markdown("#### 🆕 Datos del Personal Entrante")
            c_ent1, c_ent2, c_ent3 = st.columns(3)
            with c_ent1:
                ent_nombre = st.text_input("Nombre (Entrante) *")
                ent_profesion = st.text_input("Profesión *")
            with c_ent2:
                ent_apellido = st.text_input("Apellido (Entrante) *")
                ent_grado = st.selectbox("Grado de Instrucción *", GRADOS_INSTRUCCION)
            with c_ent3:
                ent_cedula = st.text_input("Cédula (Entrante) *")
                ent_correo = st.text_input("Correo Electrónico *", placeholder="ejemplo@correo.com")

            st.warning("📌 **Recordatorio:** Enviar la solicitud escrita y documentos del personal entrante")

            submitted = st.form_submit_button("Enviar Solicitud de Sustitución", use_container_width=True)

            if submitted:
                ubicacion_ok = validar_datos_ubicacion(subtipo, area_trabajo, nombre_comuna, codigo_situr)
                faltan_datos = not all([
                    nombre_solicitante, cedula_solicitante, ubicacion_ok,
                    sal_nombre, sal_apellido, sal_cedula,
                    ent_nombre, ent_apellido, ent_cedula, ent_profesion, ent_correo
                ])
                if motivo_sust == "Cese" and not razon_cese.strip():
