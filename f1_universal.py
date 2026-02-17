import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os

# ==============================================================================
# 1. CONFIGURACIÓN E IMPORTACIÓN DE DATOS
# ==============================================================================
st.set_page_config(page_title="F1 Data Hub Pro", layout="wide", page_icon="🏎️")
import os
PATH = os.path.dirname(__file__) # Esto le dice: "busca en la misma carpeta donde está este script"

# Función global para evitar la notación científica (ej: 2e+03 -> 2393)
def format_pts(val):
    if pd.isna(val): return "0"
    return f"{val:.2f}".rstrip('0').rstrip('.') if val % 1 != 0 else f"{int(val)}"

@st.cache_data
def cargar_datos_globales():
    drivers = pd.read_csv(os.path.join(PATH, 'drivers.csv'), sep=';', encoding='utf-8')
    constructors = pd.read_csv(os.path.join(PATH, 'constructors.csv'), sep=';', encoding='utf-8')
    races = pd.read_csv(os.path.join(PATH, 'races.csv'), sep=';', encoding='utf-8')
    results = pd.read_csv(os.path.join(PATH, 'results.csv'), sep=';', encoding='utf-8')
    circuits = pd.read_csv(os.path.join(PATH, 'circuits.csv'), sep=';', encoding='utf-8')
    qualifying = pd.read_csv(os.path.join(PATH, 'qualifying.csv'), sep=';', encoding='utf-8')
    
    try:
        sprints = pd.read_csv(os.path.join(PATH, 'sprint_results.csv'), sep=';', encoding='utf-8')
    except:
        sprints = pd.DataFrame(columns=['raceId', 'driverId', 'points'])

    for df in [drivers, constructors, races, results, circuits, qualifying, sprints]:
        df.columns = df.columns.str.strip()

    results['grid'] = pd.to_numeric(results['grid'], errors='coerce').fillna(0).astype(int)
    results['rank'] = results['rank'].astype(str).str.strip() 
    qualifying['position'] = pd.to_numeric(qualifying['position'], errors='coerce').fillna(0).astype(int)
    races['year'] = pd.to_numeric(races['year'], errors='coerce')

    # Renombramos a 'namec' para evitar conflictos con el nombre del piloto
    drivers['name_full'] = drivers['forename'].astype(str) + " " + drivers['surname'].astype(str)
    races_clean = races.rename(columns={'name': 'race_name', 'date': 'race_date'})
    constructors_clean = constructors.rename(columns={'name': 'namec'})
    
    df_main = results.merge(races_clean[['raceId', 'year', 'round', 'race_name', 'circuitId', 'race_date']], on='raceId')
    df_main = df_main.merge(drivers[['driverId', 'name_full', 'surname', 'code', 'nationality', 'dob', 'url']], on='driverId')
    df_main = df_main.merge(constructors_clean[['constructorId', 'namec']], on='constructorId')
    
    df_main['points'] = pd.to_numeric(df_main['points'], errors='coerce').fillna(0).astype(float)
    df_main['race_date'] = pd.to_datetime(df_main['race_date'], errors='coerce')

    return df_main, drivers, constructors_clean, races_clean, circuits, qualifying, sprints

df_main, df_drivers, df_constructors, df_races, df_circuits, df_qualy, df_sprints = cargar_datos_globales()
# ==============================================================================
# 2. INTERFAZ Y NAVEGACIÓN
# ==============================================================================
st.sidebar.title("🏁 F1 Data Hub")
menu = st.sidebar.radio("Navegación:", [
    "📅 Temporada Actual", "📜 Historia & Simulador", "⏱️ Vueltas Rápidas", 
    "⏱️ Pole Positions", "👤 Pilotos", "⚔️ H2H (Cara a Cara)", 
    "🏭 Equipos", "🌍 Circuitos"
])


# ------------------------------------------------------------------------------
# SECCIÓN: TEMPORADA ACTUAL
# ------------------------------------------------------------------------------
if menu == "📅 Temporada Actual":
    st.title("📅 Temporada Actual")
    year_now = df_main['year'].max()
    df_now = df_main[df_main['year'] == year_now]
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🏆 Mundial de Pilotos")
        rank_p = df_now.groupby(['name_full', 'namec'])['points'].sum().reset_index().sort_values('points', ascending=False)
        rank_p['points'] = rank_p['points'].apply(format_pts)
        st.dataframe(rank_p.rename(columns={'name_full':'Piloto', 'namec':'Equipo', 'points':'Puntos'}), use_container_width=True)
    with col2:
        st.subheader("🏭 Mundial de Constructores")
        rank_c = df_now.groupby('namec')['points'].sum().reset_index().sort_values('points', ascending=False)
        rank_c['points'] = rank_c['points'].apply(format_pts)
        st.dataframe(rank_c.rename(columns={'namec':'Equipo', 'points':'Puntos'}), use_container_width=True)

# ------------------------------------------------------------------------------
# SECCIÓN: HISTORIA & SIMULADOR (LOGICA UNIFICADA + DESEMPATE VR MODERNO)
# ------------------------------------------------------------------------------
elif menu == "📜 Historia & Simulador":
    st.title("Simulador de Puntuación Histórica")
    
    # 1. INTERFAZ (Definimos todo antes de los cálculos)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        year_sel = st.selectbox("Selecciona Año", range(df_main['year'].max(), 1949, -1), key="sim_year")
    with c2:
        SISTEMAS = {
            "🟢 Original del Año": "original",
            "2025-2026 (Sin VR)": {"pts": {1:25, 2:18, 3:15, 4:12, 5:10, 6:8, 7:6, 8:4, 9:2, 10:1}, "vr": False},
            "2019-2024 (+1 VR)": {"pts": {1:25, 2:18, 3:15, 4:12, 5:10, 6:8, 7:6, 8:4, 9:2, 10:1}, "vr": True},
            "2003-2009": {"pts": {1:10, 2:8, 3:6, 4:5, 5:4, 6:3, 7:2, 8:1}, "vr": False},
            "1991-2002": {"pts": {1:10, 2:6, 3:4, 4:3, 5:2, 6:1}, "vr": False},
            "1961-1990": {"pts": {1:9, 2:6, 3:4, 4:3, 5:2, 6:1}, "vr": False},
            "1950-1960 (+1 VR)": {"pts": {1:8, 2:6, 3:4, 4:3, 5:2}, "vr": True}
        }
        sistema_sel = st.selectbox("Sistema de Puntuación", list(SISTEMAS.keys()))
        conf = SISTEMAS[sistema_sel]
    with c3:
        st.write("") 
        st.write("") 
        modo_realista = st.toggle("Modo Realista (Descartes)", value=True, help="Aplica las reglas de descartes históricas.")

    # 2. FILTRADO Y PUNTOS BASE
    df_sim = df_main[df_main['year'] == year_sel].copy()

    if conf == "original":
        df_sim['puntos_calc'] = df_sim['points']
    else:
        # Lógica de puntos compartidos (indispensable para años 50)
        df_sim['compartidos'] = df_sim.groupby(['raceId', 'positionOrder'])['driverId'].transform('count')
        df_sim['puntos_calc'] = df_sim['positionOrder'].map(conf['pts']).fillna(0)
        df_sim['puntos_calc'] = df_sim['puntos_calc'] / df_sim['compartidos']

    # 3. DESCARTES (MODO REALISTA)
    if modo_realista:
        reglas_mitades = {1967: (6, 5, 4), 1979: (7, 4, 4), 1980: (7, 5, 5)}
        descartes_simples = {
            (1950, 1953): 4, (1954, 1957): 5, (1958, 1958): 6, (1959, 1959): 5,
            (1960, 1960): 6, (1961, 1962): 5, (1963, 1965): 6, (1966, 1966): 5,
            (1968, 1968): 10, (1969, 1969): 9, (1970, 1970): 11, (1971, 1971): 9,
            (1972, 1972): 10, (1973, 1975): 12, (1976, 1978): 14, (1981, 1990): 11
        }

        if year_sel in reglas_mitades:
            corte, m1, m2 = reglas_mitades[year_sel]
            df_sim = df_sim.sort_values(['driverId', 'round'])
            mitad1, mitad2 = df_sim[df_sim['round'] <= corte].copy(), df_sim[df_sim['round'] > corte].copy()
            for m_df, m_val in [(mitad1, m1), (mitad2, m2)]:
                m_df = m_df.sort_values(['driverId', 'puntos_calc'], ascending=[True, False])
                m_df['rank_m'] = m_df.groupby('driverId').cumcount() + 1
                m_df.loc[m_df['rank_m'] > m_val, 'puntos_calc'] = 0
            df_sim = pd.concat([mitad1, mitad2])
        else:
            n_best = 999
            for (ini, fin), val in descartes_simples.items():
                if ini <= year_sel <= fin: n_best = val; break
            if n_best != 999:
                df_sim = df_sim.sort_values(['driverId', 'puntos_calc'], ascending=[True, False])
                df_sim['rank_p'] = df_sim.groupby('driverId').cumcount() + 1
                df_sim.loc[df_sim['rank_p'] > n_best, 'puntos_calc'] = 0

    # 4. RANKING FINAL
    ranking = df_sim.groupby(['driverId', 'name_full']).agg(
        Puntos_Carrera=('puntos_calc', 'sum'),
        Victorias=('positionOrder', lambda x: (x == 1).sum()),
        Podios=('positionOrder', lambda x: (x <= 3).sum())
    ).reset_index()

    # 5. VUELTAS RÁPIDAS (Lógica de desempate)
    if conf != "original" and conf.get('vr'):
        vr_df = df_sim[df_sim['rank'].astype(str) == "1"].copy()
        if not vr_df.empty:
            vr_df['fastestLap'] = pd.to_numeric(vr_df['fastestLap'], errors='coerce')
            vr_df = vr_df.sort_values(by=['raceId', 'fastestLap', 'positionOrder'], ascending=[True, True, True], na_position='last')
            vr_df = vr_df.drop_duplicates(subset=['raceId'], keep='first')
            if "2019" in sistema_sel:
                vr_df = vr_df[vr_df['positionOrder'] <= 10]
            vr_pts_total = vr_df.groupby('driverId').size().reset_index(name='vr_pts')
            ranking = ranking.merge(vr_pts_total, on='driverId', how='left').fillna(0)
            ranking['Puntos_Carrera'] += ranking['vr_pts']
            ranking.drop(columns=['vr_pts'], inplace=True)

    # 6. SPRINTS
    if conf == "original" and year_sel >= 2021:
        ids_races = df_races[df_races['year'] == year_sel]['raceId']
        s_pts = df_sprints[df_sprints['raceId'].isin(ids_races)].groupby('driverId')['points'].sum().reset_index()
        ranking = ranking.merge(s_pts, on='driverId', how='left').fillna(0)
        ranking['Puntos_Carrera'] += ranking['points']
        ranking.drop(columns=['points'], inplace=True)

    # 7. VISUALIZACIÓN RANKING
    ranking = ranking.sort_values(['Puntos_Carrera', 'Victorias', 'Podios'], ascending=False).reset_index(drop=True)
    ranking.index += 1
    st.subheader(f"🏆 Clasificación Final {year_sel}")
    st.dataframe(ranking[['name_full', 'Puntos_Carrera', 'Victorias', 'Podios']].rename(
        columns={'name_full':'Piloto', 'Puntos_Carrera':'Puntos'}
    ), use_container_width=True)
    
    st.plotly_chart(px.bar(ranking.head(10), x='name_full', y='Puntos_Carrera', color='Puntos_Carrera'), use_container_width=True)

    # 8. EXPANDIBLES (DETALLE POR CARRERA)
    st.markdown("---")
    st.subheader(f"🏁 Resultados Detallados por Carrera")
    lista_carreras = df_sim[['round', 'race_name', 'raceId']].drop_duplicates().sort_values('round')

    for _, row_race in lista_carreras.iterrows():
        r_id, r_name, r_num = row_race['raceId'], row_race['race_name'], row_race['round']
        res_gp = df_sim[df_sim['raceId'] == r_id].copy()
        
        # Puntos brutos para el visor (usando compartidos si no es original)
        if conf == "original":
            res_gp['puntos_visual'] = res_gp['points']
        else:
            res_gp['puntos_visual'] = res_gp['positionOrder'].map(conf['pts']).fillna(0)
            # Aquí restauramos la división de puntos compartidos que se había perdido
            res_gp['puntos_visual'] = res_gp['puntos_visual'] / res_gp['compartidos']

        res_gp = res_gp.sort_values('positionOrder')
        res_gp['Info'] = ""
        mask_fl = res_gp['rank'].astype(str) == "1"
        res_gp.loc[mask_fl, 'Info'] = "FL"

        if conf != "original" and conf.get('vr'):
            vr_candidatos = res_gp[mask_fl].copy()
            if not vr_candidatos.empty:
                if "1950-1960" in sistema_sel:
                    pts_repartir = 1 / len(vr_candidatos)
                    for d_id in vr_candidatos['driverId']:
                        res_gp.loc[res_gp['driverId'] == d_id, 'puntos_visual'] += pts_repartir
                else:
                    vr_candidatos = vr_candidatos.sort_values(by=['fastestLap', 'positionOrder'], na_position='last')
                    ganador_potencial = vr_candidatos.iloc[0]
                    if "2019" not in sistema_sel or ganador_potencial['positionOrder'] <= 10:
                        res_gp.loc[res_gp['driverId'] == ganador_potencial['driverId'], 'puntos_visual'] += 1

        with st.expander(f"📍 Ronda {r_num}: {r_name}"):
            tabla_show = res_gp[['positionOrder', 'name_full', 'puntos_visual', 'Info']].rename(
                columns={'positionOrder': 'Pos', 'name_full': 'Piloto', 'puntos_visual': 'Puntos'}
            )
            tabla_show['Puntos'] = tabla_show['Puntos'].apply(lambda x: f"{x:.2f}".rstrip('0').rstrip('.') if x % 1 != 0 else f"{int(x)}")
            st.dataframe(tabla_show.set_index('Pos'), use_container_width=True)
# ------------------------------------------------------------------------------
# SECCIÓN: VUELTAS RÁPIDAS
# ------------------------------------------------------------------------------
elif menu == "⏱️ Vueltas Rápidas":
    st.title("⏱️ Registro de Vueltas Rápidas")
    y_vr = st.selectbox("Año:", range(df_main['year'].max(), 1949, -1))
    data_vr = df_main[(df_main['year'] == y_vr) & (df_main['rank'] == "1")].sort_values('round')
    if not data_vr.empty:
        st.dataframe(data_vr[['race_name', 'name_full', 'fastestLapTime']].rename(columns={'race_name':'GP', 'name_full':'Piloto', 'fastestLapTime':'Tiempo'}), use_container_width=True)
    else:
        st.warning("No hay datos de VR para este año.")

# ------------------------------------------------------------------------------
# SECCIÓN: POLE POSITIONS (CORREGIDA PARA AÑOS PRE-2006)
# ------------------------------------------------------------------------------
elif menu == "⏱️ Pole Positions":
    st.title("⏱️ Registro de Pole Positions")
    y_p = st.selectbox("Selecciona Año:", range(df_main['year'].max(), 1949, -1))
    
    # 1. Intentamos obtener datos de la tabla de clasificación
    p_data = df_qualy.merge(df_races[df_races['year'] == y_p], on='raceId')
    
    # Limpieza crucial: Convertir el texto "\N" en un valor nulo real (NaN)
    p_data = p_data.replace(r'\\N', pd.NA, regex=True)
    
    # Filtramos por el que quedó en posición 1
    p_data = p_data[p_data['position'] == 1]

    if not p_data.empty:
        p_data = p_data.merge(df_drivers[['driverId', 'name_full']], on='driverId')
        
        # LÓGICA DE TIEMPOS: 
        # Intentamos Q3 (2006-actualidad), si no Q2, si no Q1 (años antiguos).
        # Usamos bfill (backfill) sobre las columnas de tiempo para pillar el primero que exista
        tiempos_cols = ['q1', 'q2', 'q3']
        # Nos quedamos con el último tiempo registrado (que es el más rápido/final)
        p_data['Tiempo'] = p_data['q3'].fillna(p_data['q2']).fillna(p_data['q1']).fillna("N/A")
        
        res = p_data[['race_name', 'name_full', 'Tiempo']].sort_values('race_name')
        st.dataframe(res.rename(columns={'race_name': 'Gran Premio', 'name_full': 'Piloto'}), use_container_width=True)
        
    else:
        # 2. FALLBACK: Si no hay datos en qualifying, usamos results.csv (grid 1)
        # Esto es lo que usaremos para los años donde solo has metido el nombre en results
        p_back = df_main[(df_main['year'] == y_p) & (df_main['grid'] == 1)]
        
        if not p_back.empty:
            st.info(f"Mostrando poles de {y_p} basadas en la parrilla de salida.")
            
            # Si por casualidad añadiste una columna de tiempo en results.csv, cámbiala aquí:
            if 'qualifying_time' in p_back.columns:
                 st.dataframe(p_back[['race_name', 'name_full', 'qualifying_time']].rename(
                     columns={'race_name': 'Gran Premio', 'name_full': 'Piloto', 'qualifying_time': 'Tiempo'}), 
                     use_container_width=True)
            else:
                st.dataframe(p_back[['race_name', 'name_full']].rename(
                    columns={'race_name': 'Gran Premio', 'name_full': 'Piloto'}), 
                    use_container_width=True)
        else:
            st.error(f"No se han encontrado registros de Pole Positions para {y_p}.")

# ------------------------------------------------------------------------------
# SECCIÓN: PILOTOS (ESTADÍSTICAS REORDENADAS Y MEDIA SIN DNF)
# ------------------------------------------------------------------------------
elif menu == "👤 Pilotos":
    st.title("👤 Perfil del Piloto")
    
    piloto = st.selectbox("Selecciona Piloto:", df_drivers.sort_values('name_full')['name_full'])
    
    # Datos base
    info_p = df_drivers[df_drivers['name_full'] == piloto].iloc[0]
    id_p = info_p['driverId']
    s = df_main[df_main['driverId'] == id_p].copy()
    sprint_p = df_sprints[df_sprints['driverId'] == id_p]
    
    # --- CÁLCULOS DE TÍTULOS ---
    campeones = df_main.groupby(['year', 'name_full'])['points'].sum().reset_index()
    idx_campeones = campeones.groupby('year')['points'].idxmax()
    lista_campeones = campeones.loc[idx_campeones]
    titulos = len(lista_campeones[lista_campeones['name_full'] == piloto])

    # --- 1. CABECERA ---
    estrellas = "⭐" * titulos if titulos > 0 else ""
    st.header(f"{info_p['name_full']} {estrellas}")

    st.markdown("<br>", unsafe_allow_html=True)
    bio1, bio2, bio3 = st.columns(3)
    with bio1:
        st.markdown(f"<p style='text-align: center;'><b>Nacionalidad:</b><br>{info_p['nationality']}</p>", unsafe_allow_html=True)
    with bio2:
        st.markdown(f"<p style='text-align: center;'><b>Fecha de Nacimiento:</b><br>{info_p['dob']}</p>", unsafe_allow_html=True)
    with bio3:
        texto_wdc = f"🏆 {titulos} WDC" if titulos > 0 else "0 WDC"
        st.markdown(f"<p style='text-align: center;'><b>Campeonatos:</b><br>{texto_wdc}</p>", unsafe_allow_html=True)

    st.markdown("---")

    # --- 2. CÁLCULOS AVANZADOS ---
    # Filtrar solo carreras terminadas para la Posición Final Media (quitamos DNFs)
    # En el dataset, positionText suele ser un número si terminó, y una letra (R, D, E, W) si no.
    carreras_terminadas = s[s['positionText'].str.isnumeric()].copy()
    avg_finish = carreras_terminadas['positionOrder'].mean() if not carreras_terminadas.empty else 0
    
    # Otros cálculos
    total_poles = len(s[s['grid'] == 1])
    total_vr = len(s[s['rank'] == "1"]) if 'rank' in s.columns else 0
    avg_grid = s[s['grid'] > 0]['grid'].mean() # Solo grids válidos
    pts_totales = s['points'].sum() + (sprint_p['points'].sum() if not sprint_p.empty else 0)

    st.subheader("📊 Estadísticas Históricas")
    
    # FILA 1: LOS GRANDES ÉXITOS (Lo más importante)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Victorias", len(s[s['positionOrder'] == 1]))
    m2.metric("Podios", len(s[s['positionOrder'] <= 3]))
    m3.metric("GPs Disputados", len(s))
    m4.metric("Puntos Totales", format_pts(pts_totales))

    # FILA 2: RENDIMIENTO Y VELOCIDAD (Estadísticas secundarias)
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Pole Positions", total_poles)
    m6.metric("Vueltas Rápidas", total_vr)
    m7.metric("Parrilla Media", f"{avg_grid:.1f}º")
    # Mostramos que es solo sobre carreras terminadas
    m8.metric("Final Medio*", f"{avg_finish:.1f}º", help="Calculado solo sobre carreras terminadas (excluye DNFs)")

    st.markdown("---")

    # --- 3. ANÁLISIS POR TEMPORADA Y GRÁFICOS ---
    # (El resto del código se mantiene igual que antes)
    años_disponibles = sorted(s['year'].unique(), reverse=True)
    año_sel = st.selectbox("Revisar temporada específica:", años_disponibles)
    df_año = s[s['year'] == año_sel].sort_values('round')
    
    if not df_año.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"Puntos {año_sel}", format_pts(df_año['points'].sum()))
        c2.metric("Mejor Resultado", f"{int(df_año['positionOrder'].min())}º")
        abandonos = len(df_año[~df_año['positionText'].str.isnumeric()])
        c3.metric("Abandonos", abandonos)
        c4.metric("Escudería", df_año['namec'].iloc[-1])

        with st.expander(f"Ver tabla de resultados de {año_sel}"):
            tabla_año = df_año[['round', 'race_name', 'grid', 'positionOrder', 'points']].copy()
            tabla_año.columns = ['Ronda', 'Gran Premio', 'Parrilla', 'Final', 'Puntos']
            st.dataframe(tabla_año.set_index('Ronda'), use_container_width=True)

    # --- GRÁFICOS ---
    st.markdown("---")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("📊 Puntos por Año")
        hist_año = s.groupby('year')['points'].sum().reset_index()
        st.plotly_chart(px.bar(hist_año, x="year", y="points", color="points", template="plotly_dark", color_continuous_scale="Reds"), use_container_width=True)
    with col_g2:
        st.subheader("📈 Evolución de Puntos")
        prog_total = s.sort_values(['year', 'round']).reset_index(drop=True)
        prog_total['Acumulado'] = prog_total['points'].cumsum()
        fig_prog = px.line(prog_total, x=prog_total.index, y="Acumulado", template="plotly_dark")
        fig_prog.update_traces(line_color='#FF4B4B', fill='tozeroy')
        st.plotly_chart(fig_prog, use_container_width=True)

   # --- LÓGICA DE DNF PRECISA ---
    # IDs de status que indican que el coche cruzó la meta o clasificó (Finished + n Laps)
    status_ok = [1, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

    # --- 7. ANÁLISIS POR ESCUDERÍA (ORDEN CRONOLÓGICO) ---
    st.markdown("---")
    st.subheader("🏎️ Rendimiento por Escudería")
    st.write("Estadísticas detalladas ordenadas cronológicamente por debut en el equipo:")

    stats_equipo = []
    for equipo in s['namec'].unique():
        df_e = s[s['namec'] == equipo]
        
        # Guardamos el primer año que corrió con ellos para ordenar
        primer_anio = df_e['year'].min()
        
        # Puntos del piloto en el equipo
        pts_piloto = df_e['points'].sum()
        
        # Temporadas totales en este equipo
        num_temporadas = df_e['year'].nunique()
        
        # Puntos totales del equipo mientras el piloto estuvo ahí
        races_ids = df_e['raceId'].unique()
        pts_totales_equipo = df_main[(df_main['raceId'].isin(races_ids)) & (df_main['namec'] == equipo)]['points'].sum()
        
        # % de aportación
        porc_puntos = (pts_piloto / pts_totales_equipo * 100) if pts_totales_equipo > 0 else 0
        
        # DNFs (CORREGIDO USANDO statusId)
        dnfs = len(df_e[~df_e['statusId'].isin(status_ok)])
        
        stats_equipo.append({
            "Debut": primer_anio,
            "Escudería": equipo,
            "Temporadas": num_temporadas,
            "GPs": len(df_e),
            "Victorias": len(df_e[df_e['positionOrder'] == 1]),
            "Podios": len(df_e[df_e['positionOrder'] <= 3]),
            "Poles": len(df_e[df_e['grid'] == 1]),
            "VR": len(df_e[df_e['rank'] == "1"]) if 'rank' in df_e.columns else 0,
            "DNFs": dnfs,
            "Puntos": format_pts(pts_piloto),
            "% Puntos Equipo": f"{porc_puntos:.1f}%"
        })

    df_stats_e = pd.DataFrame(stats_equipo)
    
    # ORDEN CRONOLÓGICO: Del primer debut al último
    df_stats_e = df_stats_e.sort_values(by="Debut", ascending=True)
    
    # Quitamos la columna 'Debut' de la vista final si prefieres que no se vea el año suelto
    # pero que mantenga el orden.
    st.dataframe(df_stats_e.drop(columns=["Debut"]).set_index("Escudería"), use_container_width=True)

    # --- 8. ANÁLISIS DE ABANDONOS (DNFs) - CORREGIDO SIN FLECHAS ---
    st.markdown("---")
    col_dnf1, col_dnf2 = st.columns([1, 2])
    
    with col_dnf1:
        st.subheader("❌ Análisis de DNFs")
        # CORREGIDO USANDO statusId
        total_dnf = len(s[~s['statusId'].isin(status_ok)])
        ratio_dnf = (total_dnf / len(s)) * 100 if len(s) > 0 else 0
        
        # Usamos columnas pequeñas o markdown para evitar la flecha del delta de st.metric
        st.metric("Total Abandonos", total_dnf)
        st.markdown(f"""
            <div style="margin-top: -15px;">
                <p style="font-size: 24px; color: #808495; margin: 0;">
                    {ratio_dnf:.1f}% <span style="font-size: 14px;">del total</span>
                </p>
            </div>
        """, unsafe_allow_html=True)
        st.caption("*Carreras no finalizadas sobre el total de participaciones.")

    with col_dnf2:
        # CORREGIDO USANDO statusId
        dnf_por_anio = s[~s['statusId'].isin(status_ok)].groupby('year').size().reset_index(name='DNFs')
        if not dnf_por_anio.empty:
            fig_dnf = px.bar(
                dnf_por_anio, 
                x='year', 
                y='DNFs', 
                title="Abandonos por Temporada",
                template="plotly_dark"
            )
            fig_dnf.update_traces(marker_color='#FFD700') 
            fig_dnf.update_layout(
                xaxis_title="Año", 
                yaxis_title="Número de DNFs",
                hovermode="x unified"
            )
            st.plotly_chart(fig_dnf, use_container_width=True)
        else:
            st.write("Este piloto no tiene abandonos registrados.")


# ------------------------------------------------------------------------------
# SECCIÓN: CARA A CARA (H2H) - VERSIÓN ULTRA COMPLETA
# ------------------------------------------------------------------------------
elif menu == "⚔️ H2H (Cara a Cara)":
    st.title("⚔️ Head-to-Head (H2H)")

    # 1. SELECTORES
    col_sel1, col_sel2 = st.columns(2)
    lista_pilotos = df_drivers.sort_values('name_full')['name_full'].tolist()
    
    with col_sel1:
        p1 = st.selectbox("🏎️ Piloto 1:", lista_pilotos, index=lista_pilotos.index("Fernando Alonso") if "Fernando Alonso" in lista_pilotos else 0)
    with col_sel2:
        p2 = st.selectbox("🏎️ Piloto 2:", lista_pilotos, index=lista_pilotos.index("Lewis Hamilton") if "Lewis Hamilton" in lista_pilotos else 1)

    col_opt1, col_opt2 = st.columns([2, 1])
    with col_opt1:
        modo_h2h = st.radio("Filtro de enfrentamiento:", ["Todas las veces en pista", "Solo como compañeros de equipo"], horizontal=True)
    with col_opt2:
        modo_realista = st.toggle("🚀 Aplicar descartes históricos", value=True)

    if p1 == p2:
        st.warning("⚠️ Selecciona dos pilotos distintos.")
    else:
        id1 = df_drivers[df_drivers['name_full'] == p1]['driverId'].iloc[0]
        id2 = df_drivers[df_drivers['name_full'] == p2]['driverId'].iloc[0]

        # 2. FILTRADO Y DESCARTES (Lógica mantenida)
        races_p1 = df_main[df_main['driverId'] == id1]
        races_p2 = df_main[df_main['driverId'] == id2]

        if modo_h2h == "Solo como compañeros de equipo":
            common = pd.merge(races_p1[['raceId', 'constructorId', 'year']], 
                              races_p2[['raceId', 'constructorId']], on=['raceId', 'constructorId'])
        else:
            common = pd.merge(races_p1[['raceId', 'year']], races_p2[['raceId']], on='raceId')

        if common.empty:
            st.error(f"❌ No hay coincidencias.")
        else:
            races_ids_totales = common['raceId'].unique()
            anios_compartidos = sorted(common['year'].unique(), reverse=True)
            filtro_t = st.selectbox("📅 Temporada:", ["Histórico Completo"] + [str(a) for a in anios_compartidos])

            def aplicar_reglas_descarte(df_año, year_sel):
                df_sim = df_año.copy()
                df_sim['puntos_calc'] = df_sim['points']
                reglas_mitades = {1967: (6, 5, 4), 1979: (7, 4, 4), 1980: (7, 5, 5)}
                descartes_simples = {(1950, 1953): 4, (1954, 1957): 5, (1958, 1958): 6, (1959, 1959): 5, (1960, 1960): 6, (1961, 1962): 5, (1963, 1965): 6, (1966, 1966): 5, (1968, 1968): 10, (1969, 1969): 9, (1970, 1970): 11, (1971, 1971): 9, (1972, 1972): 10, (1973, 1975): 12, (1976, 1978): 14, (1981, 1990): 11}
                if year_sel in reglas_mitades:
                    corte, m1, m2 = reglas_mitades[year_sel]
                    df_sim = df_sim.sort_values('round')
                    mitad1 = df_sim[df_sim['round'] <= corte].sort_values('puntos_calc', ascending=False).copy()
                    mitad2 = df_sim[df_sim['round'] > corte].sort_values('puntos_calc', ascending=False).copy()
                    mitad1['rank_m'] = range(1, len(mitad1)+1); mitad2['rank_m'] = range(1, len(mitad2)+1)
                    mitad1.loc[mitad1['rank_m'] > m1, 'puntos_calc'] = 0; mitad2.loc[mitad2['rank_m'] > m2, 'puntos_calc'] = 0
                    df_sim = pd.concat([mitad1, mitad2])
                else:
                    n_best = 999
                    for (ini, fin), val in descartes_simples.items():
                        if ini <= year_sel <= fin: n_best = val; break
                    if n_best != 999:
                        df_sim = df_sim.sort_values('puntos_calc', ascending=False)
                        df_sim['rank_p'] = range(1, len(df_sim)+1)
                        df_sim.loc[df_sim['rank_p'] > n_best, 'puntos_calc'] = 0
                return df_sim

            anios_a_procesar = anios_compartidos if filtro_t == "Histórico Completo" else [int(filtro_t)]
            races_validas = races_ids_totales if filtro_t == "Histórico Completo" else common[common['year']==int(filtro_t)]['raceId'].unique()
            
            f1_list, f2_list = [], []
            for y in anios_a_procesar:
                d_y1 = races_p1[races_p1['year'] == y].copy()
                d_y2 = races_p2[races_p2['year'] == y].copy()
                if modo_realista:
                    d_y1 = aplicar_reglas_descarte(d_y1, y)
                    d_y2 = aplicar_reglas_descarte(d_y2, y)
                else:
                    d_y1['puntos_calc'], d_y2['puntos_calc'] = d_y1['points'], d_y2['points']
                f1_list.append(d_y1[d_y1['raceId'].isin(races_validas)])
                f2_list.append(d_y2[d_y2['raceId'].isin(races_validas)])

            df_h2h_1 = pd.concat(f1_list)
            df_h2h_2 = pd.concat(f2_list)

            # --- COMPARACIÓN DIRECTA (AHEAD) ---
            merged_comp = pd.merge(
                df_h2h_1[['raceId', 'positionOrder', 'grid', 'statusId']].rename(columns={'positionOrder':'p1_pos', 'grid':'p1_grid', 'statusId':'p1_stat'}),
                df_h2h_2[['raceId', 'positionOrder', 'grid', 'statusId']].rename(columns={'positionOrder':'p2_pos', 'grid':'p2_grid', 'statusId':'p2_stat'}),
                on='raceId'
            )
            
            ahead_race = len(merged_comp[merged_comp['p1_pos'] < merged_comp['p2_pos']])
            ahead_grid = len(merged_comp[merged_comp['p1_grid'] < merged_comp['p2_grid']])
            dnf1 = len(df_h2h_1[~df_h2h_1['statusId'].isin([1, 11, 12, 13, 14])]) # 1 es Finished, 11-14 son +Laps
            dnf2 = len(df_h2h_2[~df_h2h_2['statusId'].isin([1, 11, 12, 13, 14])])

            # --- RENDERIZADO ---
            def row(v1, lab, v2, invertido=False):
                # invertido=True para DNFs (menos es mejor)
                if v1 == v2: c1 = c2 = "#FFF"
                elif v1 > v2: c1, c2 = ("#FFF", "#00FF00") if invertido else ("#00FF00", "#FFF")
                else: c1, c2 = ("#00FF00", "#FFF") if invertido else ("#FFF", "#00FF00")
                
                t1 = f"{v1:.1f}" if isinstance(v1, (float, np.floating)) else str(v1)
                t2 = f"{v2:.1f}" if isinstance(v2, (float, np.floating)) else str(v2)
                st.markdown(f'<div style="display:flex; justify-content:space-between; align-items:center; padding:10px; border-bottom:1px solid rgba(255,255,255,0.1);"><div style="color:{c1}; font-size:22px; font-weight:800; width:20%;">{t1}</div><div style="color:#888; text-align:center; font-size:12px; text-transform:uppercase; width:60%;">{lab}</div><div style="color:{c2}; font-size:22px; font-weight:800; width:20%; text-align:right;">{t2}</div></div>', unsafe_allow_html=True)

            row(df_h2h_1['puntos_calc'].sum(), "Puntos Válidos", df_h2h_2['puntos_calc'].sum())
            row(len(df_h2h_1[df_h2h_1['positionOrder']==1]), "Victorias", len(df_h2h_2[df_h2h_2['positionOrder']==1]))
            row(len(df_h2h_1[df_h2h_1['positionOrder']<=3]), "Podios", len(df_h2h_2[df_h2h_2['positionOrder']<=3]))
            row(len(df_h2h_1[df_h2h_1['grid']==1]), "Pole Positions", len(df_h2h_2[df_h2h_2['grid']==1]))
            st.write("") # Espaciador
            row(ahead_race, "Delante en Carrera", (len(merged_comp) - ahead_race))
            row(ahead_grid, "Delante en Clasificación", (len(merged_comp) - ahead_grid))
            row(df_h2h_1['puntos_calc'].sum()/len(df_h2h_1) if len(df_h2h_1)>0 else 0, "Eficiencia (Pts/GP)", df_h2h_2['puntos_calc'].sum()/len(df_h2h_2) if len(df_h2h_2)>0 else 0)
            row(dnf1, "Abandonos (DNFs)", dnf2, invertido=True)
            row(len(df_h2h_1), "GPs Compartidos", len(df_h2h_2))

            # --- GRÁFICA ---
            st.markdown("<br>### 📈 Evolución Acumulada", unsafe_allow_html=True)
            d1_g = df_h2h_1.sort_values(['year', 'round']).copy()
            d2_g = df_h2h_2.sort_values(['year', 'round']).copy()
            d1_g['cum'] = d1_g['puntos_calc'].cumsum()
            d2_g['cum'] = d2_g['puntos_calc'].cumsum()
            df_plot = pd.merge(d1_g[['year','round','race_name','cum']].rename(columns={'cum':p1}), d2_g[['year','round','cum']].rename(columns={'cum':p2}), on=['year','round'])
            if not df_plot.empty:
                df_plot['Carrera'] = df_plot['year'].astype(str) + " " + df_plot['race_name']
                fig = px.line(df_plot, x='Carrera', y=[p1, p2], template="plotly_dark", color_discrete_map={p1:"#FF4B4B", p2:"#00D4FF"})
                fig.update_layout(hovermode="x unified", xaxis_showticklabels=False)
                st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------------------
# SECCIÓN: EQUIPOS (CON DESCARTES HISTÓRICOS Y SPRINT RACES)
# ------------------------------------------------------------------------------
elif menu == "🏭 Equipos":
    st.title("🏭 Perfil de la Escudería")
    
    # --- 1. SELECTORES ---
    equipo = st.selectbox("Selecciona Equipo:", df_constructors.sort_values('namec')['namec'])
    
    modo_realista = st.toggle("🚀 Aplicar reglas históricas (WCC)", value=True, 
                              help="Aplica descartes (hasta 1978), suma de Sprints y la regla de 'solo puntúa el mejor coche del equipo' (pre-1979).")

    # --- 2. PREPARACIÓN DE DATOS ---
    info_e = df_constructors[df_constructors['namec'] == equipo].iloc[0]
    id_e = info_e['constructorId']
    
    # Filtramos datos del equipo seleccionado
    d_e = df_main[df_main['constructorId'] == id_e].copy()
    sprint_e = df_sprints[df_sprints['constructorId'] == id_e].copy() if 'df_sprints' in globals() else pd.DataFrame()

    # --- 3. FUNCIÓN PROCESADORA DE PUNTOS (ESPECÍFICA WCC) ---
    def procesar_puntos_equipo(df_input, df_sprints_input, realista):
        df_res = df_input.copy()
        
        # A) Integración de Sprints (Puntos brutos)
        if not df_sprints_input.empty:
            pts_sprint = df_sprints_input.groupby(['raceId', 'driverId'])['points'].sum().reset_index()
            pts_sprint.columns = ['raceId', 'driverId', 'puntos_sprint']
            df_res = pd.merge(df_res, pts_sprint, on=['raceId', 'driverId'], how='left')
            df_res['puntos_sprint'] = df_res['puntos_sprint'].fillna(0)
            df_res['puntos_calc'] = df_res['points'] + df_res['puntos_sprint']
        else:
            df_res['puntos_sprint'] = 0
            df_res['puntos_calc'] = df_res['points']

        if not realista:
            return df_res

        # B) REGLA DEL MEJOR COCHE (WCC pre-1979)
        # Solo el coche mejor posicionado sumaba puntos para el equipo
        def filtrar_mejor_coche(group):
            if group.name[0] < 1979:
                idx_mejor = group['positionOrder'].idxmin()
                mask = group.index != idx_mejor
                group.loc[mask, 'puntos_calc'] = 0
            return group

        df_res = df_res.groupby(['year', 'raceId'], group_keys=False).apply(filtrar_mejor_coche)

        # C) DESCARTES DEL MUNDIAL DE CONSTRUCTORES (WCC)
        # A diferencia de pilotos, el WCC eliminó descartes en 1979.
        reglas_mitades_wcc = {
            1967: (6, 5, 4), 1968: (6, 5, 5), 1969: (6, 5, 4), 1970: (7, 6, 5),
            1971: (6, 5, 4), 1972: (6, 5, 5), 1973: (8, 7, 6), 1974: (8, 7, 6),
            1975: (8, 7, 5), 1976: (8, 7, 7), 1977: (9, 8, 7), 1978: (8, 7, 7)
        }
        descartes_simples_wcc = {
            (1958, 1958): 6, (1959, 1959): 5, (1960, 1960): 6, 
            (1961, 1962): 5, (1963, 1965): 6, (1966, 1966): 5
        }

        final_dfs = []
        for y in df_res['year'].unique():
            df_y = df_res[df_res['year'] == y].copy()
            
            # Los descartes de equipo solo existieron de 1958 a 1978
            if 1958 <= y <= 1978:
                if y in reglas_mitades_wcc:
                    corte, m1, m2 = reglas_mitades_wcc[y]
                    mitad1 = df_y[df_y['round'] <= corte].copy()
                    mitad2 = df_y[df_y['round'] > corte].copy()
                    
                    for m_df, m_val in [(mitad1, m1), (mitad2, m2)]:
                        m_df = m_df.sort_values('puntos_calc', ascending=False)
                        m_df['rank_e'] = m_df.groupby('constructorId').cumcount() + 1
                        m_df.loc[m_df['rank_e'] > m_val, 'puntos_calc'] = 0
                    df_y = pd.concat([mitad1, mitad2])
                    
                else:
                    n_best = 999
                    for (ini, fin), val in descartes_simples_wcc.items():
                        if ini <= y <= fin: n_best = val; break
                    if n_best != 999:
                        df_y = df_y.sort_values('puntos_calc', ascending=False)
                        df_y['rank_e'] = df_y.groupby('constructorId').cumcount() + 1
                        df_y.loc[df_y['rank_e'] > n_best, 'puntos_calc'] = 0

            final_dfs.append(df_y)
        
        return pd.concat(final_dfs).sort_index() if final_dfs else df_res

    # Procesamos los puntos finales del equipo
    d_e_final = procesar_puntos_equipo(d_e, sprint_e, modo_realista)

    # --- 4. INTERFAZ Y MÉTRICAS ---
    st.header(f"{info_e['namec']}")

    col1, col2, col3 = st.columns(3)
    col1.metric("País", info_e['nationality'])
    col2.metric("Temporadas", f"{d_e['year'].min()} - {d_e['year'].max()}")
    col3.metric("Puntos Válidos WCC", f"{d_e_final['puntos_calc'].sum():.1f}")

    # --- 5. GRÁFICA: APORTACIÓN DE PILOTOS ---
    st.subheader("🏆 Pilotos que más puntuaron para el equipo")
    
    # Agrupamos por piloto usando los puntos procesados (con descartes si aplica)
    top_pilotos = d_e_final.groupby('name_full')['puntos_calc'].sum().nlargest(10).reset_index()
    
    fig_pilotos = px.bar(top_pilotos, x='puntos_calc', y='name_full', orientation='h',
                        template="plotly_dark", 
                        labels={'puntos_calc': 'Puntos aportados al WCC', 'name_full': 'Piloto'},
                        color='puntos_calc', color_continuous_scale="Viridis")
    fig_pilotos.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_pilotos, use_container_width=True)

    # --- 6. TABLA DETALLADA ---
    with st.expander("Ver desglose anual por piloto (Puntos WCC)"):
        # Mostramos los puntos que realmente sumaron para el equipo cada año
        tabla_resumen = d_e_final.groupby(['year', 'name_full']).agg({
            'puntos_calc': 'sum',
            'puntos_sprint': 'sum',
            'positionOrder': lambda x: (x == 1).sum()
        }).rename(columns={
            'puntos_calc': 'Puntos WCC',
            'puntos_sprint': 'Puntos Sprint',
            'positionOrder': 'Victorias'
        }).reset_index()
        
        st.dataframe(tabla_resumen.sort_values(['year', 'Puntos WCC'], ascending=[False, False]), use_container_width=True)
# ------------------------------------------------------------------------------
# SECCIÓN: CIRCUITOS
# ------------------------------------------------------------------------------
elif menu == "🌍 Circuitos":
    st.title("🌍 Análisis de Circuitos")
    circ = st.selectbox("Selecciona Circuito:", df_circuits['name'].sort_values())
    c_info = df_circuits[df_circuits['name'] == circ].iloc[0]
    
    st.write(f"**Ubicación:** {c_info['location']}, {c_info['country']}")
    st.map(pd.DataFrame({'lat': [c_info['lat']], 'lon': [c_info['lng']]}))
    
    ganadores = df_main[(df_main['circuitId'] == c_info['circuitId']) & (df_main['positionOrder'] == 1)]
    st.dataframe(ganadores[['year', 'race_name', 'name_full']].sort_values('year', ascending=False), use_container_width=True)
