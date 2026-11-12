import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Gestión de Movimientos de Plantilla", 
    page_icon="📋", 
    layout="wide"
)

if "solicitudes" not in st.session_state:
    st.session_state.solicitudes = []

AREAS_RESPONSABLES = [
    "Talento Humano y Gestión de Personal",
    "Coordinación Operativa y Territorial (UTL)",
    "Administración, Finanzas y Presupuesto"
]

TIPOS_SOLICITUD = [
    "Desincorporación",
    "Cese",
    "Cambio de rol o cargo",
    "Sustitución"
]

AREAS_ORIGEN = [
    "UTL (Unidad Territorial Local)",
    "Coordinación Regional",
    "Formación y Gestión del Conocimiento",
    "Administración Central"
]

st.title("👥 Sistema de Control de Movimientos de Plantilla")
st.markdown("Plataforma para la gestión y trámite de solicitudes de personal entre áreas operativas.")

menu = st.sidebar.selectbox("Navegación", ["Nueva Solicitud", "Bandeja de Solicitudes y Estatus"])

if menu == "Nueva Solicitud":
    st.header("Formulario de Solicitud de Movimiento")
    st.markdown("Complete los datos requeridos para remitir la solicitud al área responsable correspondiente.")
    
    with st.form("form_movimiento_personal"):
        st.subheader("1. Identificación del Solicitante y Destino")
        col1, col2 = st.columns(2)
        
        with col1:
            nombre_solicitante = st.text_input("Nombre y Apellido del Solicitante")
            cedula_solicitante = st.text_input("Cédula de Identidad (Solicitante)")
            area_origen = st.selectbox("Área / Adscripción de Origen", AREAS_ORIGEN)
            
        with col2:
            cargo_solicitante = st.text_input("Cargo del Solicitante")
            area_destino = st.selectbox("Área Responsable Destino", AREAS_RESPONSABLES)

        st.markdown("---")
        st.subheader("2. Detalle del Movimiento de Personal")
        
        col3, col4 = st.columns(2)
        with col3:
            tipo_solicitud = st.selectbox("Tipo de Solicitud", TIPOS_SOLICITUD)
            nombre_afectado = st.text_input("Nombre del Trabajador / Formador Afectado")
            cedula_afectado = st.text_input("Cédula del Trabajador Afectado")
            
        with col4:
            cargo_actual = st.text_input("Cargo Actual del Trabajador")
            cargo_nuevo = st.text_input("Nuevo Cargo / Rol Propuesto (Si aplica)")
            
        justificacion = st.text_area("Justificación o Motivo Técnico del Movimiento")
        
        submitted = st.form_submit_button("Enviar Solicitud al Área Responsable")
        
        if submitted:
            if not nombre_solicitante or not nombre_afectado or not justificacion:
                st.error("Por favor complete los campos obligatorios (Nombre del solicitante, afectado y justificación).")
            else:
                nueva_solicitud = {
                    "ID": len(st.session_state.solicitudes) + 1,
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Solicitante": nombre_solicitante,
                    "Área Origen": area_origen,
                    "Área Destino": area_destino,
                    "Tipo de Solicitud": tipo_solicitud,
                    "Personal Afectado": nombre_afectado,
                    "Cédula Afectado": cedula_afectado,
                    "Cargo Actual": cargo_actual,
                    "Cargo Nuevo": cargo_nuevo if cargo_nuevo else "N/A",
                    "Justificación": justificacion,
                    "Estado": "Pendiente"
                }
                st.session_state.solicitudes.append(nueva_solicitud)
                st.success("¡Solicitud registrada y enviada exitosamente al área correspondiente!")

elif menu == "Bandeja de Solicitudes y Estatus":
    st.header("Bandeja General de Movimientos")
    
    if len(st.session_state.solicitudes) == 0:
        st.info("No hay solicitudes registradas en el sistema actualmente.")
    else:
        df_solicitudes = pd.DataFrame(st.session_state.solicitudes)
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_destino = st.selectbox("Filtrar por Área Responsable", ["Todas"] + AREAS_RESPONSABLES)
        with col_f2:
            filtro_tipo = st.selectbox("Filtrar por Tipo de Solicitud", ["Todas"] + TIPOS_SOLICITUD)
            
        df_filtrado = df_solicitudes.copy()
        if filtro_destino != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Área Destino"] == filtro_destino]
        if filtro_tipo != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Tipo de Solicitud"] == filtro_tipo]
            
        st.dataframe(df_filtrado, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Gestión y Actualización de Estatus")
        
        if not df_filtrado.empty:
            sol_id = st.selectbox("Seleccione el ID de la solicitud a gestionar", df_filtrado["ID"].tolist())
            
            idx = next((i for i, item in enumerate(st.session_state.solicitudes) if item["ID"] == sol_id), None)
            
            if idx is not None:
                actual_status = st.session_state.solicitudes[idx]["Estado"]
                nuevo_estado = st.selectbox(
                    "Cambiar Estatus", 
                    ["Pendiente", "En Revisión", "Aprobado", "Rechazado"],
                    index=["Pendiente", "En Revisión", "Aprobado", "Rechazado"].index(actual_status) if actual_status in ["Pendiente", "En Revisión", "Aprobado", "Rechazado"] else 0
                )
                
                if st.button("Actualizar Estatus"):
                    st.session_state.solicitudes[idx]["Estado"] = nuevo_estado
                    st.success(f"La solicitud #{sol_id} ha sido actualizada a: **{nuevo_estado}**")
                    st.rerun()
