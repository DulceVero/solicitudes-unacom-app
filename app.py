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

MOTIVOS_SALIDA = ["Renuncia", "Cambio de rol", "Cese"]

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
    "ID", "Fecha", "Solicitante", "Cédula Solicitante", "Cargo Solicitante",
    "Área Origen", "Área Destino", "Tipo de Solicitud", "Estado Geográfico",
    "Saliente Nombre", "Saliente Apellido", "Saliente Cédula",
    "Motivo", "Detalle Motivo",
    "Entrante Nombre", "Entrante Apellido", "Entrante Cédula",
    "Entrante Profesión", "Entrante Grado Instrucción", "Entrante Correo",
    "Cargo Actual", "Cargo Nuevo", "Observaciones", "Estado"
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
    # Verificar si los encabezados coinciden o están vacíos
    encabezados_actuales = sheet.row_values(1)
    if not encabezados_actuales:
        sheet.append_row(COLUMNAS_ESPERADAS)
    elif encabezados_actuales != COLUMNAS_ESPERADAS:
        # Actualiza la fila 1 si tenías los encabezados de la versión anterior
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

if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = None

# --- FUNCIÓN DE LOGIN ---
def pantalla_login():
    st.title("Movimientos en Plantillas de Personal")
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

# --- VISTA 1: SOLICITANTE (FORMULARIO DINÁMICO) ---
def vista_solicitante(datos_usuario):
    st.header("📝 Solicitud de Movimiento de Personal")
    st.info(f"Conectado como: **{datos_usuario['nombre']}** | Adscripción: **{datos_usuario['area_origen']}**")
    
    # Paso 1: Selección del tipo de solicitud (FUERA del form para reactividad inmediata)
    tipo_solicitud = st.radio(
        "¿Qué movimiento de plantilla desea tramitar?",
        TIPOS_SOLICITUD,
        horizontal=True
    )
    
    st.markdown("---")
    
    # Controles dinámicos previos al envío (ej. Motivo de Cese en Sustitución)
    motivo_seleccionado = "N/A"
    razon_cese = "N/A"
    
    if tipo_solicitud == "Sustitución":
        st.subheader(f" Formulario de {tipo_solicitud}")
        
        # Selector de motivo fuera del form para mostrar la caja de texto si elige 'Cese'
        col_m1, col_m2 = st.columns([1, 2])
        with col_m1:
            motivo_seleccionado = st.selectbox("Motivo de la sustitución *", MOTIVOS_SALIDA)
        with col_m2:
            if motivo_seleccionado == "Cese":
                razon_cese = st.text_input("Especifique la razón del cese *", placeholder="Indique el motivo detallado del cese...")
            else:
                st.write("")
                st.caption("Si selecciona 'Cese', se habilitará un campo para detallar la razón.")

        with st.form("form_sustitucion", clear_on_submit=True):
            # Datos generales
            st.markdown("#### Datos de Ubicación y Destino")
            c_g1, c_g2, c_g3 = st.columns(3)
            with c_g1:
                estado_vzla = st.selectbox("Estado *", ESTADOS_VENEZUELA)
            with c_g2:
                area_destino = st.selectbox("Área Responsable Destino *", datos_usuario["areas_permitidas"])
            with c_g3:
                cargo_solicitante = st.text_input("Cargo del Solicitante *", placeholder="Ej. Coordinador UTL")

            c_g4, c_g5 = st.columns(2)
            with c_g4:
                nombre_solicitante = st.text_input("Nombre y Apellido del Solicitante *", value=datos_usuario["nombre"])
            with c_g5:
                cedula_solicitante = st.text_input("Cédula del Solicitante *", placeholder="Ej. V-12345678")

            st.markdown("---")
            # Sección Personal Saliente
            st.markdown("#### 👤 Datos del Personal Saliente")
            c_sal1, c_sal2, c_sal3 = st.columns(3)
            with c_sal1:
                sal_nombre = st.text_input("Nombre (Saliente) *")
            with c_sal2:
                sal_apellido = st.text_input("Apellido (Saliente) *")
            with c_sal3:
                sal_cedula = st.text_input("Cédula (Saliente) *")

            st.markdown("---")
            # Sección Personal Entrante
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

            # Recordatorio solicitado
            st.warning("📌 **Recordatorio:** Enviar la solicitud escrita y documentos del personal entrante")

            submitted = st.form_submit_button("Enviar Solicitud de Sustitución", use_container_width=True)

            if submitted:
                # Validaciones de campos obligatorios
                faltan_datos = not all([
                    nombre_solicitante, cedula_solicitante, cargo_solicitante,
                    sal_nombre, sal_apellido, sal_cedula,
                    ent_nombre, ent_apellido, ent_cedula, ent_profesion, ent_correo
                ])
                if motivo_seleccionado == "Cese" and not razon_cese.strip():
                    st.error("⚠️ Debe escribir la razón del cese antes de enviar la solicitud.")
                elif faltan_datos:
                    st.error("⚠️ Por favor complete todos los campos obligatorios marcados con (*).")
                else:
                    with st.spinner("Registrando sustitución en Google Sheets..."):
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
                            "Tipo de Solicitud": "Sustitución",
                            "Estado Geográfico": estado_vzla,
                            "Saliente Nombre": sal_nombre,
                            "Saliente Apellido": sal_apellido,
                            "Saliente Cédula": sal_cedula,
                            "Motivo": motivo_seleccionado,
                            "Detalle Motivo": razon_cese if motivo_seleccionado == "Cese" else "N/A",
                            "Entrante Nombre": ent_nombre,
                            "Entrante Apellido": ent_apellido,
                            "Entrante Cédula": ent_cedula,
                            "Entrante Profesión": ent_profesion,
                            "Entrante Grado Instrucción": ent_grado,
                            "Entrante Correo": ent_correo,
                            "Cargo Actual": "N/A",
                            "Cargo Nuevo": "N/A",
                            "Observaciones": "Sustitución registrada",
                            "Estado": "Pendiente"
                        }
                        guardar_nueva_solicitud(nueva_solicitud)
                    st.success(f"✅ ¡Solicitud de Sustitución #{nuevo_id} registrada exitosamente!")

    # --- FORMULARIOS PARA LAS OTRAS 3 OPCIONES (Estructura lista para seguir personalizando) ---
    else:
        st.subheader(f"📋 Formulario de {tipo_solicitud}")
        with st.form("form_otros_movimientos", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                estado_vzla = st.selectbox("Estado *", ESTADOS_VENEZUELA)
                nombre_solicitante = st.text_input("Nombre y Apellido del Solicitante *", value=datos_usuario["nombre"])
            with c2:
                area_destino = st.selectbox("Área Responsable Destino *", datos_usuario["areas_permitidas"])
                cedula_solicitante = st.text_input("Cédula del Solicitante *")
            with c3:
                cargo_solicitante = st.text_input("Cargo del Solicitante *")

            st.markdown("---")
            st.markdown("#### Datos del Personal")
            cp1, cp2, cp3 = st.columns(3)
            with cp1:
                p_nombre = st.text_input("Nombre *")
                cargo_actual = st.text_input("Cargo Actual")
            with cp2:
                p_apellido = st.text_input("Apellido *")
                cargo_nuevo = st.text_input("Nuevo Cargo / Rol (si aplica)")
            with cp3:
                p_cedula = st.text_input("Cédula *")
                p_correo = st.text_input("Correo Electrónico")

            observaciones = st.text_area("Justificación / Detalle de la solicitud *")

            submitted_otro = st.form_submit_button(f"Enviar Solicitud de {tipo_solicitud}", use_container_width=True)
            if submitted_otro:
                if not all([nombre_solicitante, cedula_solicitante, p_nombre, p_apellido, p_cedula, observaciones]):
                    st.error("⚠️ Complete los campos obligatorios marcados con (*).")
                else:
                    with st.spinner("Guardando en Google Sheets..."):
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
                            "Estado Geográfico": estado_vzla,
                            "Saliente Nombre": p_nombre if tipo_solicitud in ["Desincorporación", "Cambio de rol"] else "N/A",
                            "Saliente Apellido": p_apellido if tipo_solicitud in ["Desincorporación", "Cambio de rol"] else "N/A",
                            "Saliente Cédula": p_cedula if tipo_solicitud in ["Desincorporación", "Cambio de rol"] else "N/A",
                            "Motivo": tipo_solicitud,
                            "Detalle Motivo": observaciones,
                            "Entrante Nombre": p_nombre if tipo_solicitud == "Incorporación" else "N/A",
                            "Entrante Apellido": p_apellido if tipo_solicitud == "Incorporación" else "N/A",
                            "Entrante Cédula": p_cedula if tipo_solicitud == "Incorporación" else "N/A",
                            "Entrante Profesión": "N/A",
                            "Entrante Grado Instrucción": "N/A",
                            "Entrante Correo": p_correo if p_correo else "N/A",
                            "Cargo Actual": cargo_actual if cargo_actual else "N/A",
                            "Cargo Nuevo": cargo_nuevo if cargo_nuevo else "N/A",
                            "Observaciones": observaciones,
                            "Estado": "Pendiente"
                        }
                        guardar_nueva_solicitud(nueva_solicitud)
                    st.success(f"✅ ¡Solicitud #{nuevo_id} de {tipo_solicitud} enviada exitosamente!")

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
            filtro_estado = st.selectbox("Filtrar por Estado", ["Todos"] + ESTADOS_SOLICITUD)
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
