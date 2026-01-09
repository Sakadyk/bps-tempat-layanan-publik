import streamlit as st
import pandas as pd
import json
import plotly.express as px
import os
from datetime import datetime

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="Dashboard Pelayanan Publik",
    page_icon="🚆",
    layout="wide"
)

# ==========================================
# 2. FUNGSI LOAD DATA
# ==========================================
@st.cache_data
def load_data():
    file_path = 'data_dashboard.json'
    if not os.path.exists(file_path):
        return None
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    # Pastikan koordinat float
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    
    # Cek ketersediaan data popular times
    # (Asumsi: jika dictionary kosong atau None, berarti tidak ada data)
    df['has_data'] = df['popular_times'].apply(lambda x: bool(x) and len(x) > 0)
    
    # Mapping Warna & Label Sentimen
    df['sentiment_label'] = df['sentiment_score'].map({1: 'Negatif', 2: 'Netral', 3: 'Positif'})
    df['color_code'] = df['sentiment_score'].map({1: '#FF4B4B', 2: '#FFC107', 3: '#09AB3B'})
    
    return df

def get_live_busyness(row, day, hour):
    """Cari persentase keramaian (default 0 jika tutup atau tidak ada data)"""
    if not row['has_data']:
        return 0
        
    popular_times = row.get('popular_times', {})
    schedule = popular_times.get(day, [])
    for slot in schedule:
        if slot['hour'] == hour:
            return slot['percentage']
    return 0

# ==========================================
# 3. PROSES DATA UTAMA
# ==========================================
df = load_data()

if df is None:
    st.error("File 'data_dashboard.json' tidak ditemukan.")
    st.stop()

# Waktu Saat Ini
now = datetime.now()
days_map = {0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis", 4: "Jumat", 5: "Sabtu", 6: "Minggu"}
curr_day = days_map[now.weekday()]
curr_hour = now.hour

# Waktu Data Diambil
latest_scrape_time = df['timestamp'].max() if 'timestamp' in df.columns else "-"

# Hitung keramaian real-time
df['current_busy_level'] = df.apply(lambda x: get_live_busyness(x, curr_day, curr_hour), axis=1)

# ==========================================
# 4. SIDEBAR (FILTER)
# ==========================================
st.sidebar.header("🎛️ Kontrol Dashboard")

# Widget Informasi Waktu
st.sidebar.markdown("### 🕒 Waktu Saat Ini")
st.sidebar.info(f"{curr_day}, {curr_hour}:00 WIB")

st.sidebar.markdown("### 📅 Data Diupdate Per")
st.sidebar.warning(f"{latest_scrape_time}")

st.sidebar.divider()

# Pilihan Tampilan
view_mode = st.sidebar.radio("Mode Tampilan:", ["🗺️ Peta Sebaran", "🔍 Detail Lokasi"])

# Jika mode detail, pilih lokasinya
selected_loc_name = None
if view_mode == "🔍 Detail Lokasi":
    selected_loc_name = st.sidebar.selectbox("Pilih Lokasi:", df['name'].unique())

# ==========================================
# 5. LAYOUT UTAMA
# ==========================================
st.title("🚆 Dashboard Pelayanan Publik Tangsel")

if view_mode == "🗺️ Peta Sebaran":
    # --- MODE 1: OVERVIEW PETA ---
    
    # PERSIAPAN DATA UNTUK PETA
    # 1. Tentukan Kategori Warna (Sentimen vs Tidak Ada Data)
    def get_map_category(row):
        if not row['has_data']:
            return "Tidak Ada Data Popular Time"
        return row['sentiment_label'] # Positif/Netral/Negatif

    df['map_category'] = df.apply(get_map_category, axis=1)

    # 2. Tentukan Ukuran Titik
    # Kita tambah +10 agar titik yang nilainya 0 (tutup/tidak ada data) tetap terlihat
    # Jika ada data: Size = Level Keramaian + 10
    # Jika tidak ada data: Size = 8 (Fixed kecil)
    df['map_size'] = df.apply(lambda x: (x['current_busy_level'] + 10) if x['has_data'] else 8, axis=1)

    # Metric Ringkas di Atas
    c1, c2, c3 = st.columns(3)
    
    # Metric 1: Breakdown Ketersediaan Data
    total_loc = len(df)
    data_avail = df['has_data'].sum()
    c1.metric("Total Titik Pantau", f"{total_loc}", f"{data_avail} Lokasi punya data Popular Time")
    
    # Metric 2: Rata-rata keramaian (hanya dari yg punya data & buka)
    active_df = df[(df['has_data']) & (df['current_busy_level'] > 0)]
    avg_busy = active_df['current_busy_level'].mean()
    val_busy = int(avg_busy) if not pd.isna(avg_busy) else 0
    c2.metric("Rata-rata Keramaian Kota", f"{val_busy}%")
    
    # Metric 3: Lokasi Teramai
    if not active_df.empty:
        busiest = active_df.loc[active_df['current_busy_level'].idxmax()]
        c3.metric("Lokasi Terpadat", f"{busiest['name']}", f"{busiest['current_busy_level']}%")
    else:
        c3.metric("Lokasi Terpadat", "-")

    st.subheader("Peta & Status Terkini")
    
    # Peta Sebaran (FIX: Menggunakan scatter_map)
    fig_map = px.scatter_map(
        df,
        lat="latitude",
        lon="longitude",
        hover_name="name",
        hover_data={
            "map_category": True, 
            "current_busy_level": True, 
            "map_size": False, # Sembunyikan data teknis ini dari tooltip
            "latitude": False,
            "longitude": False
        },
        color="map_category",
        # Custom Warna: Sentimen (Merah/Kuning/Hijau) & No Data (Abu-abu)
        color_discrete_map={
            'Negatif': '#FF4B4B', 
            'Netral': '#FFC107', 
            'Positif': '#09AB3B',
            'Tidak Ada Data Popular Time': '#9E9E9E' # Abu-abu
        },
        size="map_size", # Ukuran dinamis
        size_max=30,
        zoom=11,
        height=500
    )
    # FIX: map_style menggantikan mapbox_style
    fig_map.update_layout(map_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0})
    
    # Scroll Zoom Enabled (FIX: width="stretch")
    st.plotly_chart(fig_map, width="stretch", config={'scrollZoom': True})
    
    st.info("ℹ️ **Keterangan Peta:** Ukuran lingkaran menunjukkan tingkat keramaian saat ini. Titik **Abu-abu** menandakan lokasi tersebut tidak memiliki data *Live Popular Times* di Google Maps.")

else:
    # --- MODE 2: DETAIL LOKASI ---
    
    loc = df[df['name'] == selected_loc_name].iloc[0]
    
    st.markdown(f"## 📍 {loc['name']}")
    
    has_pop_times = loc['has_data']

    # --- Metrics Section ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("##### 🚦 Keramaian Sekarang")
        if has_pop_times:
            # Menggunakan curr_day (Real-time) untuk metric angka
            st.markdown(f"<h2 style='color:blue'>{loc['current_busy_level']}%</h2>", unsafe_allow_html=True)
            st.caption(f"Status per hari ini ({curr_day}, {curr_hour}:00)")
        else:
            st.markdown("<h3 style='color:gray'>Data Tidak Tersedia</h3>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("##### 😊 Sentimen Publik")
        color = loc['color_code']
        st.markdown(f"<h2 style='color:{color}'>{loc['sentiment_label']}</h2>", unsafe_allow_html=True)
        
    with col3:
        st.markdown("##### 📅 Data Diambil")
        st.markdown(f"<h4 style='color:gray'>{loc.get('timestamp', '-')}</h4>", unsafe_allow_html=True)

    st.divider()

    # --- Grafik & Analisis ---
    g_col1, g_col2 = st.columns([2, 1])

    with g_col1:
        # Header dengan Kolom Filter Hari
        c_head1, c_head2 = st.columns([2, 1])
        with c_head1:
            st.subheader("📊 Grafik Tren Keramaian")
        with c_head2:
            # Dropdown untuk memilih hari grafik (Default: Hari Ini)
            days_list = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
            # Cari index hari ini untuk default value
            current_day_idx = datetime.now().weekday()
            selected_chart_day = st.selectbox("Pilih Hari:", days_list, index=current_day_idx, label_visibility="collapsed")
        
        if has_pop_times:
            try:
                # Ambil data sesuai hari yang DIPILIH di dropdown
                chart_data_source = loc['popular_times'].get(selected_chart_day, [])
                
                if chart_data_source:
                    chart_df = pd.DataFrame(chart_data_source)
                    
                    # Logika Pewarnaan:
                    # - Jika hari yg dipilih == hari ini, highlight jam sekarang merah
                    # - Jika hari lain, semua abu-abu biasa
                    colors = ['#E0E0E0'] * len(chart_df)
                    
                    if selected_chart_day == curr_day:
                        try:
                            idx = chart_df[chart_df['hour'] == curr_hour].index[0]
                            colors[idx] = '#FF4B4B' # Merah (Jam Sekarang)
                        except IndexError:
                            pass
                    else:
                        # Jika melihat hari lain, beri warna biru muda agar beda
                        colors = ['#90CAF9'] * len(chart_df)

                    fig = px.bar(
                        chart_df, x='hour', y='percentage',
                        labels={'hour': 'Jam', 'percentage': 'Ramai (%)'},
                        height=350,
                        title=f"Estimasi Keramaian: {selected_chart_day}"
                    )
                    fig.update_traces(marker_color=colors)
                    fig.update_layout(xaxis=dict(tickmode='linear'), margin=dict(l=20, r=20, t=40, b=20))
                    # FIX: width="stretch" menggantikan use_container_width=True
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info(f"Tempat ini tutup/tidak ada data pada hari {selected_chart_day}.")
                
            except KeyError:
                st.warning(f"Terjadi kesalahan membaca data grafik.")
        else:
            st.warning("⚠️ Google Maps tidak menyediakan data 'Popular Times' untuk lokasi ini.")

    with g_col2:
        st.subheader("🤖 Analisis Singkat")
        st.info(loc.get('summary', '-'))
        
        st.write("**Topik Utama:**")
        topics = loc.get('topics', [])
        if topics:
            tags_html = " ".join([
                f"<span style='background-color:#f0f2f6; padding:4px 8px; margin:2px; border-radius:4px; font-size:14px'>{t}</span>" 
                for t in topics
            ])
            st.markdown(tags_html, unsafe_allow_html=True)
        else:
            st.text("-")

st.caption("Dashboard Monitoring v2.3 - Fixed Deprecation Warnings")