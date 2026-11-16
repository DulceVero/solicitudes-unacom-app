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

# Columnas unificadas y ordenadas estrictamente
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

def reparar_o_inicializar_hoja(sheet):
    """Verifica los encabezados y asegura que la estructura sea coherente."""
    fila_1 = sheet.row_values(1)
    if not fila_1 or fila_1 != COLUMNAS_ESPERADAS:
        sheet.update("A1", [COLUMNAS_ESPERADAS])

def cargar_datos():
    try:
        sheet = conectar_google_sheets()
        reparar_o_inicializar_hoja(sheet)
        registros = sheet.get_all_records(expected_headers=COLUMNAS_ESPERADAS)
        
        # Limpieza de DataFrame para evitar columnas desordenadas o vacías
        if registros:
            df = pd.DataFrame(registros)
            for col in COLUMNAS_ESPERADAS:
                if col not in df.columns:
                    df[col] = "N/A"
            df = df[COLUMNAS_ESPERADAS] # Ordena estrictamente las columnas
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

def actualizar_estatus_en_sheets(solicitud_id, nuevo_estado):
    sheet = conectar_google_sheets()
    reparar_o_inicializar_hoja(sheet)
    registros = sheet.get_all_records(expected_headers=COLUMNAS_ESPERADAS)
    df = pd.DataFrame(registros)
    if not df.empty and "ID" in df.columns:
        indices = df.index[df["ID"].astype(str) == str(solicitud_id)].tolist()
        if indices:
            fila_sheet = indices[0] + 2
            col_estado = COLUMNAS_ESPERADAS.index("Estado") + 1
            sheet.update_cell(fila_sheet, col_estado, nuevo_estado)

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
                sal_cedula = st.number_input("Cédula (Saliente) *", min_value=0, step=1, format="%d")

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
                ent_cedula = st.number_input("Cédula (Entrante) *", min_value=0, step=1, format="%d")
                ent_correo = st.text_input("Correo Electrónico *", placeholder="ejemplo@correo.com")

            st.warning("📌 **Recordatorio:** Enviar la solicitud escrita y documentos del personal entrante")

            submitted = st.form_submit_button("Enviar Solicitud de Sustitución", use_container_width=True)

            if submitted:
                ubicacion_ok = validar_datos_ubicacion(subtipo, area_trabajo, nombre_comuna, codigo_situr)
                cedulas_validas = (cedula_solicitante > 0) and (sal_cedula > 0) and (ent_cedula > 0)
                faltan_datos = not all([
                    nombre_solicitante.strip(), ubicacion_ok,
                    sal_nombre.strip(), sal_apellido.strip(),
                    ent_nombre.strip(), ent_apellido.strip(), ent_profesion.strip(), ent_correo.strip()
                ])
                if motivo_sust == "Cese" and not razon_cese.strip():
                    st.error("⚠️ Debe escribir la razón del cese antes de enviar la solicitud.")
                elif faltan_datos:
                    st.error("⚠️ Por favor complete todos los campos obligatorios marcados con (*).")
                elif not cedulas_validas:
                    st.error("⚠️ Todas las cédulas deben ser mayores a 0.")
                elif not es_correo_valido(ent_correo):
                    st.error("⚠️ Ingrese un correo electrónico válido (ejemplo@dominio.com).")
                else:
                    with st.spinner("Registrando sustitución en Google Sheets..."):
                        registros_actuales = cargar_datos()
                        nuevo_id = max([int(r["ID"]) for r in registros_actuales if str(r.get("ID", "")).isdigit()], default=0) + 1

                        nueva_solicitud = {
                            "ID": nuevo_id,
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Solicitante": nombre_solicitante.strip(),
                            "Cédula Solicitante": int(cedula_solicitante),
                            "Tipo Solicitante": subtipo,
                            "Área de Trabajo": area_trabajo,
                            "Nombre de Comuna": nombre_comuna,
                            "Código SITUR": codigo_situr,
                            "Tipo de Solicitud": "Sustitución",
                            "Estado Geográfico": estado_vzla,
                            "Saliente Nombre": sal_nombre.strip(),
                            "Saliente Apellido": sal_apellido.strip(),
                            "Saliente Cédula": int(sal_cedula),
                            "Motivo": motivo_sust,
                            "Detalle Motivo": razon_cese.strip() if motivo_sust == "Cese" else "N/A",
                            "Entrante Nombre": ent_nombre.strip(),
                            "Entrante Apellido": ent_apellido.strip(),
                            "Entrante Cédula": int(ent_cedula),
                            "Profesión": ent_profesion.strip(),
                            "Grado Instrucción": ent_grado,
                            "Entrante Correo": ent_correo.strip(),
                            "Nuevo Rol": "N/A",
                            "Estado": "Pendiente"
                        }
                        guardar_nueva_solicitud(nueva_solicitud)
                    st.success(f"✅ ¡Solicitud de Sustitución #{nuevo_id} registrada exitosamente!")

    # ==========================================
    # FORMULARIO 2: INCORPORACIÓN
    # ==========================================
    elif tipo_solicitud == "Incorporación":
        st.subheader("📋 Formulario de Incorporación")
        with st.form("form_incorporacion", clear_on_submit=True):
            estado_vzla, nombre_solicitante, cedula_solicitante, area_trabajo, nombre_comuna, codigo_situr = renderizar_datos_solicitante(datos_usuario)

            st.markdown("---")
            st.markdown("#### 👤 Datos del Personal")
            cp1, cp2 = st.columns(2)
            with cp1:
                p_nombre = st.text_input("Nombre *")
                p_cedula = st.number_input("Cédula (Solo números) *", min_value=0, step=1, format="%d")
                p_grado = st.selectbox("Grado de Instrucción *", GRADOS_INSTRUCCION)
            with cp2:
                p_apellido = st.text_input("Apellido *")
                p_profesion = st.text_input("Profesión *")

            submitted_inc = st.form_submit_button("Enviar Solicitud de Incorporación", use_container_width=True)
            if submitted_inc:
                ubicacion_ok = validar_datos_ubicacion(subtipo, area_trabajo, nombre_comuna, codigo_situr)
                if not all([nombre_solicitante.strip(), ubicacion_ok, p_nombre.strip(), p_apellido.strip(), p_profesion.strip()]):
                    st.error("⚠️ Complete todos los campos obligatorios marcados con (*).")
                elif cedula_solicitante <= 0 or p_cedula <= 0:
                    st.error("⚠️ Las cédulas deben ser mayores a 0.")
                else:
                    with st.spinner("Registrando incorporación en Google Sheets..."):
                        registros_actuales = cargar_datos()
                        nuevo_id = max([int(r["ID"]) for r in registros_actuales if str(r.get("ID", "")).isdigit()], default=0) + 1

                        nueva_solicitud = {
                            "ID": nuevo_id,
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Solicitante": nombre_solicitante.strip(),
                            "Cédula Solicitante": int(cedula_solicitante),
                            "Tipo Solicitante": subtipo,
                            "Área de Trabajo": area_trabajo,
                            "Nombre de Comuna": nombre_comuna,
                            "Código SITUR": codigo_situr,
                            "Tipo de Solicitud": "Incorporación",
                            "Estado Geográfico": estado_vzla,
                            "Saliente Nombre": "N/A",
                            "Saliente Apellido": "N/A",
                            "Saliente Cédula": "N/A",
                            "Motivo": "Incorporación",
                            "Detalle Motivo": "N/A",
                            "Entrante Nombre": p_nombre.strip(),
                            "Entrante Apellido": p_apellido.strip(),
                            "Entrante Cédula": int(p_cedula),
                            "Profesión": p_profesion.strip(),
                            "Grado Instrucción": p_grado,
                            "Entrante Correo": "N/A",
                            "Nuevo Rol": "N/A",
                            "Estado": "Pendiente"
                        }
                        guardar_nueva_solicitud(nueva_solicitud)
                    st.success(f"✅ ¡Solicitud de Incorporación #{nuevo_id} enviada exitosamente!")

    # ==========================================
    # FORMULARIO 3: DESINCORPORACIÓN
    # ==========================================
    elif tipo_solicitud == "Desincorporación":
        st.subheader("📋 Formulario de Desincorporación")

        col_d1, col_d2 = st.columns([1, 2])
        with col_d1:
            motivo_desinc = st.selectbox("Motivo de desincorporación *", MOTIVOS_DESINCORPORACION)
        with col_d2:
            if motivo_desinc in ["Cese", "Otro"]:
                detalle_desinc = st.text_input(f"Especifique el motivo ({motivo_desinc}) *", placeholder="Escriba el detalle aquí...")
            else:
                detalle_desinc = "N/A"
                st.write("")
                st.caption("Si selecciona 'Cese' u 'Otro', se habilitará un campo para detallar.")

        with st.form("form_desincorporacion", clear_on_submit=True):
            estado_vzla, nombre_solicitante, cedula_solicitante, area_trabajo, nombre_comuna, codigo_situr = renderizar_datos_solicitante(datos_usuario)

            st.markdown("---")
            st.markdown("#### 👤 Datos del Personal")
            cp1, cp2 = st.columns(2)
            with cp1:
                p_nombre = st.text_input("Nombre *")
                p_cedula = st.number_input("Cédula (Solo números) *", min_value=0, step=1, format="%d")
                p_grado = st.selectbox("Grado de Instrucción *", GRADOS_INSTRUCCION)
            with cp2:
                p_apellido = st.text_input("Apellido *")
                p_profesion = st.text_input("Profesión *")

            submitted_des = st.form_submit_button("Enviar Solicitud de Desincorporación", use_container_width=True)
            if submitted_des:
                ubicacion_ok = validar_datos_ubicacion(subtipo, area_trabajo, nombre_comuna, codigo_situr)
                if motivo_desinc in ["Cese", "Otro"] and not detalle_desinc.strip():
                    st.error(f"⚠️ Debe especificar el detalle para el motivo '{motivo_desinc}'.")
                elif not all([nombre_solicitante.strip(), ubicacion_ok, p_nombre.strip(), p_apellido.strip(), p_profesion.strip()]):
                    st.error("⚠️ Complete todos los campos obligatorios marcados con (*).")
                elif cedula_solicitante <= 0 or p_cedula <= 0:
                    st.error("⚠️ Las cédulas deben ser mayores a 0.")
                else:
                    with st.spinner("Registrando desincorporación en Google Sheets..."):
                        registros_actuales = cargar_datos()
                        nuevo_id = max([int(r["ID"]) for r in registros_actuales if str(r.get("ID", "")).isdigit()], default=0) + 1

                        nueva_solicitud = {
                            "ID": nuevo_id,
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Solicitante": nombre_solicitante.strip(),
                            "Cédula Solicitante": int(cedula_solicitante),
                            "Tipo Solicitante": subtipo,
                            "Área de Trabajo": area_trabajo,
                            "Nombre de Comuna": nombre_comuna,
                            "Código SITUR": codigo_situr,
                            "Tipo de Solicitud": "Desincorporación",
                            "Estado Geográfico": estado_vzla,
                            "Saliente Nombre": p_nombre.strip(),
                            "Saliente Apellido": p_apellido.strip(),
                            "Saliente Cédula": int(p_cedula),
                            "Motivo": motivo_desinc,
                            "Detalle Motivo": detalle_desinc.strip() if motivo_desinc in ["Cese", "Otro"] else "N/A",
                            "Entrante Nombre": "N/A",
                            "Entrante Apellido": "N/A",
                            "Entrante Cédula": "N/A",
                            "Profesión": p_profesion.strip(),
                            "Grado Instrucción": p_grado,
                            "Entrante Correo": "N/A",
                            "Nuevo Rol": "N/A",
                            "Estado": "Pendiente"
                        }
                        guardar_nueva_solicitud(nueva_solicitud)
                    st.success(f"✅ ¡Solicitud de Desincorporación #{nuevo_id} enviada exitosamente!")

    # ==========================================
    # FORMULARIO 4: CAMBIO DE ROL
    # ==========================================
    elif tipo_solicitud == "Cambio de rol":
        st.subheader("📋 Formulario de Cambio de Rol")
        with st.form("form_cambio_rol", clear_on_submit=True):
            estado_vzla, nombre_solicitante, cedula_solicitante, area_trabajo, nombre_comuna, codigo_situr = renderizar_datos_solicitante(datos_usuario)

            st.markdown("---")
            st.markdown("#### 👤 Datos del Personal")
            cp1, cp2 = st.columns(2)
            with cp1:
                p_nombre = st.text_input("Nombre *")
                p_cedula = st.number_input("Cédula (Solo números) *", min_value=0, step=1, format="%d")
            with cp2:
                p_apellido = st.text_input("Apellido *")
                p_profesion = st.text_input("Profesión *")

            nuevo_rol = st.selectbox("Rol Asignado *", ROLES_CAMBIO)

            submitted_rol = st.form_submit_button("Enviar Solicitud de Cambio de Rol", use_container_width=True)
            if submitted_rol:
                ubicacion_ok = validar_datos_ubicacion(subtipo, area_trabajo, nombre_comuna, codigo_situr)
                if not all([nombre_solicitante.strip(), ubicacion_ok, p_nombre.strip(), p_apellido.strip(), p_profesion.strip()]):
                    st.error("⚠️ Complete todos los campos obligatorios marcados con (*).")
                elif cedula_solicitante <= 0 or p_cedula <= 0:
                    st.error("⚠️ Las cédulas deben ser mayores a 0.")
                else:
                    with st.spinner("Registrando cambio de rol en Google Sheets..."):
                        registros_actuales = cargar_datos()
                        nuevo_id = max([int(r["ID"]) for r in registros_actuales if str(r.get("ID", "")).isdigit()], default=0) + 1

                        nueva_solicitud = {
                            "ID": nuevo_id,
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Solicitante": nombre_solicitante.strip(),
                            "Cédula Solicitante": int(cedula_solicitante),
                            "Tipo Solicitante": subtipo,
                            "Área de Trabajo": area_trabajo,
                            "Nombre de Comuna": nombre_comuna,
                            "Código SITUR": codigo_situr,
                            "Tipo de Solicitud": "Cambio de rol",
                            "Estado Geográfico": estado_vzla,
                            "Saliente Nombre": p_nombre.strip(),
                            "Saliente Apellido": p_apellido.strip(),
                            "Saliente Cédula": int(p_cedula),
                            "Motivo": "Cambio de rol",
                            "Detalle Motivo": "N/A",
                            "Entrante Nombre": "N/A",
                            "Entrante Apellido": "N/A",
                            "Entrante Cédula": "N/A",
                            "Profesión": p_profesion.strip(),
                            "Grado Instrucción": "N/A",
                            "Entrante Correo": "N/A",
                            "Nuevo Rol": nuevo_rol,
                            "Estado": "Pendiente"
                        }
                        guardar_nueva_solicitud(nueva_solicitud)
                    st.success(f"✅ ¡Solicitud de Cambio de Rol #{nuevo_id} enviada exitosamente!")

# --- VISTA 2: RESPONSABLE DE ÁREA (BANDEJA Y GRÁFICAS EXCLUSIVAS DE SU ÁREA) ---
def vista_responsable(datos_usuario):
    area_resp = datos_usuario["area_asignada"]

    col_top1, col_top2 = st.columns([4, 1])
    with col_top1:
        st.header(f"📊 Panel de Control: Área {area_resp}")
        st.caption(f"Mostrando exclusivamente solicitudes emitidas por el perfil **{area_resp}**.")
    with col_top2:
        st.write("")
        if st.button("🔄 Actualizar Datos", use_container_width=True):
            st.rerun()

    registros = cargar_datos()

    if not registros:
        st.info("Aún no existen solicitudes registradas en la hoja de Google Sheets.")
        return

    df_total = pd.DataFrame(registros)

    if "Tipo Solicitante" in df_total.columns:
        df_area = df_total[df_total["Tipo Solicitante"].astype(str).str.strip() == area_resp].copy()
    else:
        st.warning("La base de datos aún no tiene registros clasificados por Tipo Solicitante.")
        return

    if df_area.empty:
        st.warning(f"No hay solicitudes registradas para el área **{area_resp}** en este momento.")
        return

    tab_bandeja, tab_graficas = st.tabs(["📥 Bandeja de Solicitudes y Gestión", "📈 Estadísticas y Gráficas"])

    with tab_bandeja:
        st.subheader("Filtros de Búsqueda")
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)

        with col_f1:
            filtro_cedula = st.text_input("Buscar por Cédula", placeholder="Ej. 12345678").strip()
        with col_f2:
            filtro_estado_geo = st.selectbox("Estado Geográfico", ["Todos"] + ESTADOS_VENEZUELA)
        with col_f3:
            filtro_tipo = st.selectbox("Tipo de Solicitud", ["Todos"] + TIPOS_SOLICITUD)
        with col_f4:
            filtro_estatus = st.selectbox("Estatus del Trámite", ["Todos"] + ESTADOS_SOLICITUD)

        df_filtrado = df_area.copy()

        if filtro_cedula:
            cond_sol = df_filtrado["Cédula Solicitante"].astype(str).str.contains(filtro_cedula, case=False, na=False)
            cond_sal = df_filtrado["Saliente Cédula"].astype(str).str.contains(filtro_cedula, case=False, na=False)
            cond_ent = df_filtrado["Entrante Cédula"].astype(str).str.contains(filtro_cedula, case=False, na=False)
            df_filtrado = df_filtrado[cond_sol | cond_sal | cond_ent]

        if filtro_estado_geo != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Estado Geográfico"] == filtro_estado_geo]

        if filtro_tipo != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Tipo de Solicitud"] == filtro_tipo]

        if filtro_estatus != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Estado"] == filtro_estatus]

        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Actualizar Estatus de Solicitud")

        if not df_filtrado.empty:
            col_g1, col_g2, col_g3 = st.columns([1, 1, 1])
            with col_g1:
                sol_id = st.selectbox("ID de Solicitud", df_filtrado["ID"].tolist())

            fila_sel = df_total[df_total["ID"].astype(str) == str(sol_id)]
            if not fila_sel.empty:
                actual_status = fila_sel.iloc[0]["Estado"]
                idx_status = ESTADOS_SOLICITUD.index(actual_status) if actual_status in ESTADOS_SOLICITUD else 0

                with col_g2:
                    nuevo_estado = st.selectbox(
                        "Nuevo Estatus",
                        ESTADOS_SOLICITUD,
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
        else:
            st.info("No hay registros con los filtros aplicados para actualizar estatus.")

    with tab_graficas:
        st.subheader(f"Indicadores de Gestión — Área {area_resp}")

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
                title=f"Tipos de Solicitud ({area_resp})",
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
                title=f"Distribución por Estatus ({area_resp})",
                color="Estado",
                color_discrete_map={
                    "Pendiente": "#FFA500",
                    "En Revisión": "#3498DB",
                    "Aprobado": "#2ECC71",
                    "Rechazado": "#E74C3C"
                }
            )
            st.plotly_chart(fig_estado, use_container_width=True)

# --- VISTA 3: CONSOLIDADO GENERAL (TODAS LAS ÁREAS) ---
def vista_consolidada(datos_usuario):
    col_top1, col_top2 = st.columns([4, 1])
    with col_top1:
        st.header("🌐 Tablero Consolidado General de Movimientos")
        st.caption("Vista global de solicitudes emitidas por **UTL**, **Formador** y **PNF**.")
    with col_top2:
        st.write("")
        if st.button("🔄 Actualizar Datos", use_container_width=True):
            st.rerun()

    registros = cargar_datos()

    if not registros:
        st.info("Aún no existen solicitudes registradas en la hoja de Google Sheets.")
        return

    df_total = pd.DataFrame(registros)

    tab_bandeja, tab_graficas = st.tabs(["📥 Bandeja Consolidada", "📈 Gráficas e Indicadores Globales"])

    with tab_bandeja:
        st.subheader("Filtros de Búsqueda")
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)

        with col_f1:
            filtro_ced_solicitante = st.text_input("Cédula del Solicitante", placeholder="Ej. 12345678").strip()
        with col_f2:
            filtro_estado_geo = st.selectbox("Estado (Geográfico)", ["Todos"] + ESTADOS_VENEZUELA)
        with col_f3:
            filtro_tipo = st.selectbox("Tipo de Solicitud", ["Todos"] + TIPOS_SOLICITUD)
        with col_f4:
            filtro_estatus = st.selectbox("Estatus del Trámite", ["Todos"] + ESTADOS_SOLICITUD)

        df_filtrado = df_total.copy()

        if filtro_ced_solicitante:
            df_filtrado = df_filtrado[
                df_filtrado["Cédula Solicitante"].astype(str).str.contains(filtro_ced_solicitante, case=False, na=False)
            ]

        if filtro_estado_geo != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Estado Geográfico"] == filtro_estado_geo]

        if filtro_tipo != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Tipo de Solicitud"] == filtro_tipo]

        if filtro_estatus != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Estado"] == filtro_estatus]

        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Gestión Rápida de Estatus")
        if not df_filtrado.empty:
            col_g1, col_g2, col_g3 = st.columns([1, 1, 1])
            with col_g1:
                sol_id = st.selectbox("ID de Solicitud", df_filtrado["ID"].tolist())

            fila_sel = df_total[df_total["ID"].astype(str) == str(sol_id)]
            if not fila_sel.empty:
                actual_status = fila_sel.iloc[0]["Estado"]
                idx_status = ESTADOS_SOLICITUD.index(actual_status) if actual_status in ESTADOS_SOLICITUD else 0

                with col_g2:
                    nuevo_estado = st.selectbox("Nuevo Estatus", ESTADOS_SOLICITUD, index=idx_status)
                with col_g3:
                    st.write("")
                    st.write("")
                    if st.button("Guardar Cambio de Estatus", use_container_width=True):
                        with st.spinner("Actualizando Google Sheets..."):
                            actualizar_estatus_en_sheets(sol_id, nuevo_estado)
                        st.success(f"Solicitud #{sol_id} actualizada a **{nuevo_estado}**.")
                        st.rerun()

    with tab_graficas:
        st.subheader("Resumen Ejecutivo Global")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total General", len(df_total))
        m2.metric("Solicitudes UTL", len(df_total[df_total["Tipo Solicitante"] == "UTL"]))
        m3.metric("Solicitudes Formador", len(df_total[df_total["Tipo Solicitante"] == "Formador"]))
        m4.metric("Solicitudes PNF", len(df_total[df_total["Tipo Solicitante"] == "PNF"]))

        st.markdown("---")

        g1_col1, g1_col2 = st.columns(2)

        with g1_col1:
            conteo_tipo = df_total["Tipo de Solicitud"].value_counts().reset_index()
            conteo_tipo.columns = ["Tipo de Solicitud", "Cantidad"]

            fig_tipo = px.bar(
                conteo_tipo,
                x="Tipo de Solicitud",
                y="Cantidad",
                color="Tipo de Solicitud",
                title="Cantidad por Tipo de Solicitud",
                text_auto=True
            )
            fig_tipo.update_layout(showlegend=False)
            st.plotly_chart(fig_tipo, use_container_width=True)

        with g1_col2:
            conteo_area_raw = df_total["Tipo Solicitante"].value_counts().to_dict()
            datos_areas = [
                {"Área / Perfil": area, "Cantidad": conteo_area_raw.get(area, 0)}
                for area in ["UTL", "Formador", "PNF"]
            ]
            df_areas_chart = pd.DataFrame(datos_areas)

            fig_areas = px.bar(
                df_areas_chart,
                x="Área / Perfil",
                y="Cantidad",
                color="Área / Perfil",
                title="Solicitudes por Área (UTL, Formador, PNF)",
                text_auto=True,
                color_discrete_map={
                    "UTL": "#2E86C1",
                    "Formador": "#28B463",
                    "PNF": "#D4AC0D"
                }
            )
            fig_areas.update_layout(showlegend=False)
            st.plotly_chart(fig_areas, use_container_width=True)

        st.markdown("---")

        g2_col1, g2_col2 = st.columns(2)

        with g2_col1:
            conteo_geo = df_total["Estado Geográfico"].value_counts().reset_index()
            conteo_geo.columns = ["Estado", "Cantidad"]
            conteo_geo = conteo_geo.sort_values(by="Cantidad", ascending=True)

            fig_geo = px.bar(
                conteo_geo,
                x="Cantidad",
                y="Estado",
                orientation="h",
                title="Solicitudes por Estado (Geográfico)",
                text_auto=True,
                color="Cantidad",
                color_continuous_scale="Blues"
            )
            fig_geo.update_layout(showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig_geo, use_container_width=True)

        with g2_col2:
            conteo_estatus = df_total["Estado"].value_counts().reset_index()
            conteo_estatus.columns = ["Estatus", "Cantidad"]

            fig_estatus = px.pie(
                conteo_estatus,
                names="Estatus",
                values="Cantidad",
                hole=0.4,
                title="Distribución por Estatus del Trámite",
                color="Estatus",
                color_discrete_map={
                    "Pendiente": "#FFA500",
                    "En Revisión": "#3498DB",
                    "Aprobado": "#2ECC71",
                    "Rechazado": "#E74C3C"
                }
            )
            st.plotly_chart(fig_estatus, use_container_width=True)

# --- CONTROLADOR PRINCIPAL ---
if st.session_state.usuario_actual is None:
    pantalla_login()
else:
    user = st.session_state.usuario_actual

    with st.sidebar:
        st.markdown(f"### 👤 {user['nombre']}")
        st.caption(f"Rol: **{user['rol'].upper()}**")
        if user["rol"] in ["responsable", "consolidado"]:
            st.caption(f"Alcance: **{user['area_asignada']}**")
        else:
            st.caption(f"Perfil: **{user.get('subtipo', '')}**")

        st.markdown("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.usuario_actual = None
            st.rerun()

    if user["rol"] == "solicitante":
        vista_solicitante(user)
    elif user["rol"] == "responsable":
        vista_responsable(user)
    elif user["rol"] == "consolidado":
        vista_consolidada(user)
