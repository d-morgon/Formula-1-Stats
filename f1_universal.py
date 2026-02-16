import streamlit as st
import pandas as pd
import plotly.express as px
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
# SECCIÓN: PILOTOS (FICHA TÉCNICA, ESTADÍSTICAS Y GRADIENTES)
# ------------------------------------------------------------------------------
elif menu == "👤 Pilotos":
    st.title("👤 Perfil Profesional del Piloto")
    
    # Selector de piloto
    piloto = st.selectbox("Selecciona Piloto:", df_drivers.sort_values('name_full')['name_full'])
    
    # Datos base
    info_p = df_drivers[df_drivers['name_full'] == piloto].iloc[0]
    id_p = info_p['driverId']
    s = df_main[df_main['driverId'] == id_p].copy()
    
    # --- BLOQUE 1: FICHA TÉCNICA ---
    with st.container():
        st.subheader(f"{info_p['name_full']} ({info_p['code'] if pd.notna(info_p['code']) else '---'})")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Nacionalidad:** {info_p['nationality']}")
        c2.markdown(f"**Nacimiento:** {info_p['dob']}")
        c3.markdown(f"**Equipos:** {s['namec'].nunique()}")
        c4.markdown(f"[🔗 Wikipedia]({info_p['url']})")

    st.markdown("---")

    # --- BLOQUE 2: MÉTRICAS CLAVE ---
    total_gps = len(s)
    victorias = len(s[s['positionOrder'] == 1])
    podios = len(s[s['positionOrder'] <= 3])
    pos_media = s['positionOrder'].mean()
    
    # Filtro para abandonos (asumiendo que valores de statusId != 1 son incidencias/abandonos en dataset Ergast)
    # Si no tienes statusId, una aproximación es positionText 'R', 'D', 'W' etc.
    abandonos_totales = len(s[~s['positionText'].str.isnumeric()])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Grandes Premios", total_gps)
    m2.metric("Puntos Totales", format_pts(s['points'].sum()))
    m3.metric("Victorias", victorias)
    m4.metric("Podios", podios)

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Posición Media", f"{pos_media:.1f}º")
    m6.metric("Abandonos", abandonos_totales)
    m7.metric("% Efectividad (Vic)", f"{(victorias/total_gps*100):.1f}%" if total_gps > 0 else "0%")
    m8.metric("Mejor Resultado", f"{int(s['positionOrder'].min())}º")

    st.markdown("---")

    # --- BLOQUE 3: TABLA DE RENDIMIENTO CON GRADIENTE ---
    st.subheader("📊 Análisis de Rendimiento por Temporada")
    
    años = sorted(s['year'].unique(), reverse=True)
    res_t = []
    for a in años:
        df_a = s[s['year'] == a]
        pts_p = df_a['points'].sum()
        
        # Último equipo del año
        eid = df_a['constructorId'].iloc[-1]
        enom = df_a['namec'].iloc[-1]
        
        # Puntos del equipo
        pts_e = df_main[(df_main['year'] == a) & (df_main['constructorId'] == eid)]['points'].sum()
        pct = (pts_p / pts_e * 100) if pts_e > 0 else 0
        
        # Abandonos en el año
        abs_y = len(df_a[~df_a['positionText'].str.isnumeric()])
        
        res_t.append({
            "Año": a, 
            "Equipo": enom, 
            "Mejor Pos.": int(df_a['positionOrder'].min()),
            "Abandonos": abs_y,
            "Pts Piloto": pts_p, 
            "Pts Equipo": pts_e, 
            "% Equipo": pct
        })
    
    df_res_t = pd.DataFrame(res_t)
    
    # Preparar visualización con estilo
    # Aplicamos gradiente verde al aporte al equipo y azul a los puntos
    st.dataframe(
        df_res_t.style.background_gradient(subset=['% Equipo'], cmap='Greens')
        .background_gradient(subset=['Pts Piloto'], cmap='YlGnBu')
        .format({'% Equipo': '{:.1f}%', 'Pts Piloto': '{:.0f}', 'Pts Equipo': '{:.0f}'}),
        use_container_width=True
    )

    # --- BLOQUE 4: GRÁFICO DE PUNTOS ---
    st.subheader("📈 Curva de Puntos Histórica")
    fig_pts = px.area(df_res_t.sort_values("Año"), x="Año", y="Pts Piloto", 
                     line_shape="spline", color_discrete_sequence=["#00CC96"])
    st.plotly_chart(fig_pts, use_container_width=True)
# ------------------------------------------------------------------------------
# SECCIÓN: H2H (CARA A CARA)
# ------------------------------------------------------------------------------
elif menu == "⚔️ H2H (Cara a Cara)":
    st.title("⚔️ Comparador Cara a Cara")
    col1, col2 = st.columns(2)
    p1 = col1.selectbox("Piloto 1", df_drivers['name_full'].sort_values(), index=0)
    p2 = col2.selectbox("Piloto 2", df_drivers['name_full'].sort_values(), index=1)
    
    id1 = df_drivers[df_drivers['name_full'] == p1]['driverId'].values[0]
    id2 = df_drivers[df_drivers['name_full'] == p2]['driverId'].values[0]
    
    # Carreras donde ambos participaron
    races_common = set(df_main[df_main['driverId'] == id1]['raceId']).intersection(set(df_main[df_main['driverId'] == id2]['raceId']))
    
    if races_common:
        h2h_data = df_main[df_main['raceId'].isin(races_common)]
        res = h2h_data.pivot(index='raceId', columns='driverId', values='positionOrder').dropna()
        p1_wins = (res[id1] < res[id2]).sum()
        p2_wins = (res[id2] < id1).sum() # Error corregido en lógica
        p2_wins = (res[id2] < res[id1]).sum()

        st.subheader(f"Duelos en Carrera: {len(res)}")
        c1, c2 = st.columns(2)
        c1.metric(p1, p1_wins)
        c2.metric(p2, p2_wins)
    else:
        st.warning("Estos pilotos nunca han coincidido en una carrera.")

# ------------------------------------------------------------------------------
# SECCIÓN: EQUIPOS
# ------------------------------------------------------------------------------
elif menu == "🏭 Equipos":
    st.title("🏭 Análisis de Constructores")
    equipo = st.selectbox("Selecciona Equipo:", df_constructors['team_name'].sort_values())
    d_e = df_main[df_main['team_name'] == equipo]
    
    st.metric("Puntos Históricos", f"{d_e['points'].sum():.1f}")
    
    st.subheader("Top 10 Pilotos en este equipo")
    top_p = d_e.groupby('name_full')['points'].sum().nlargest(10).reset_index()
    st.bar_chart(top_p.set_index('name_full'))

# ------------------------------------------------------------------------------
# SECCIÓN: CIRCUITOS
# ------------------------------------------------------------------------------
elif menu == "🌍 Circuitos":
    st.title("🌍 Análisis de Circuitos")
    circ = st.selectbox("Selecciona Circuito:", df_circuits['name'].sort_values())
    c_info = df_circuits[df_circuits['name'] == circ].iloc[0]
    
    st.write(f"**Ubicación:** {c_info['location']}, {c_info['country']}")
    st.map(pd.DataFrame({'lat': [c_info['lat']], 'lon': [c_info['lng']]}))
    
    st.subheader("Últimos Ganadores")
    ganadores = df_main[(df_main['circuitId'] == c_info['circuitId']) & (df_main['positionOrder'] == 1)]
    st.dataframe(ganadores[['year', 'race_name', 'name_full']].sort_values('year', ascending=False), use_container_width=True)