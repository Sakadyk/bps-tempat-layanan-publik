import streamlit as st
import pandas as pd
import json
import plotly.express as px
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="Dashboard Pelayanan Publik Tangsel",
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
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    
    # Identifikasi ketersediaan data popular times
    df['has_data'] = df['popular_times'].apply(lambda x: bool(x) and len(x) > 0)
    
    # Mapping Label Sentimen
    df['sentiment_label'] = df['sentiment_score'].map({1: 'Negatif', 2: 'Netral', 3: 'Positif'})
    
    return df

def get_live_busyness(row, day, hour):
    if not row['has_data']: return 0
    popular_times = row.get('popular_times', {})
    schedule = popular_times.get(day, [])
    for slot in schedule:
        if slot['hour'] == hour:
            return slot['percentage']
    return 0

def get_best_time(row, day):
    if not row['has_data']: return None, None
    pop_times = row.get('popular_times', {}).get(day, [])
    # Cari jam aktif (07:00 - 21:00) yang persentasenya > 0
    active_times = [p for p in pop_times if p['percentage'] > 0 and 7 <= p['hour'] <= 21]
    if active_times:
        best_slot = min(active_times, key=lambda x: x['percentage'])
        return best_slot['hour'], best_slot['percentage']
    return None, None

# ==========================================
# 3. PROSES DATA UTAMA
# ==========================================
df = load_data()
if df is None:
    st.error("File 'data_dashboard.json' tidak ditemukan.")
    st.stop()

# Waktu Saat Ini
now = datetime.now(ZoneInfo("Asia/Jakarta"))
days_map = {0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis", 4: "Jumat", 5: "Sabtu", 6: "Minggu"}
curr_day = days_map[now.weekday()]
curr_hour = now.hour

# Hitung keramaian real-time
df['current_busy_level'] = df.apply(lambda x: get_live_busyness(x, curr_day, curr_hour), axis=1)

# Format kolom teks khusus untuk Hover Peta agar ramah pengguna
def format_hover_text(row):
    status = row['sentiment_label']
    if not row['has_data']:
        return f"{status}<br>Keramaian: -"
    return f"{status}<br>Keramaian: {int(row['current_busy_level'])}%"

df['Info'] = df.apply(format_hover_text, axis=1)

# Logika Kategori Warna Peta (Tetap mempertahankan warna abu-abu untuk No Data)
def get_map_category(row):
    if not row['has_data']:
        return "Tidak Ada Data Popular Time"
    return row['sentiment_label']

df['map_category'] = df.apply(get_map_category, axis=1)

# ==========================================
# 4. SIDEBAR
# ==========================================
st.sidebar.header("🎛️ Kontrol Dashboard")
view_mode = st.sidebar.radio("Mode Tampilan:", ["🗺️ Peta Sebaran", "🔍 Detail Lokasi"])

st.sidebar.markdown("---")
st.sidebar.info(f"🕒 **Waktu Sekarang:**\n{curr_day}, {curr_hour}:00 WIB")

selected_loc_name = None
if view_mode == "🔍 Detail Lokasi":
    nav_df = df[['name', 'sentiment_label', 'current_busy_level']].copy()
    nav_df.columns = ['Lokasi', 'Sentimen', 'Ramai']
    event = st.sidebar.dataframe(
        nav_df,
        column_config={
            "Ramai": st.column_config.ProgressColumn("Ramai", format="%d%%", min_value=0, max_value=100),
        },
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    selected_index = event.selection.rows[0] if event.selection.rows else 0
    selected_loc_name = df.iloc[selected_index]['name']

# ==========================================
# 5. LAYOUT UTAMA
# ==========================================
st.title("🚆 Monitoring Kepadatan & Layanan Tangsel")

if view_mode == "🗺️ Peta Sebaran":
    # --- UI PETA ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Titik", len(df))
    c2.metric("Titik dengan Data Live", df['has_data'].sum())
    
    active_df = df[df['current_busy_level'] > 0]
    avg_busy = int(active_df['current_busy_level'].mean()) if not active_df.empty else 0
    c3.metric("Rata-rata Keramaian Kota", f"{avg_busy}%")
    
    st.subheader("Peta Sebaran Lokasi")
    
    # Peta dengan Hover yang dioptimalkan
    fig_map = px.scatter_map(
        df,
        lat="latitude",
        lon="longitude",
        hover_name="name",
        # Menggunakan kolom 'Info' yang sudah diformat sebelumnya
        hover_data={
            "Info": True,
            "latitude": False,
            "longitude": False,
            "map_category": False
        },
        color="map_category",
        color_discrete_map={
            'Negatif': '#FF4B4B', 
            'Netral': '#FFC107', 
            'Positif': '#09AB3B',
            'Tidak Ada Data Popular Time': '#9E9E9E' 
        },
        size=df.apply(lambda x: (x['current_busy_level'] + 10) if x['has_data'] else 8, axis=1),
        size_max=25,
        zoom=11,
        height=600
    )
    
    # Membersihkan label kolom di hover agar tidak muncul 'Info='
    fig_map.update_traces(hovertemplate="<b>%{hovertext}</b><br><br>%{customdata[0]}<extra></extra>")
    fig_map.update_layout(map_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig_map, width='stretch')
    
    st.info("ℹ️ **Keterangan:** Lingkaran **Abu-abu** adalah lokasi tanpa data keramaian real-time.")

else:
    # --- MODE DETAIL ---
    loc = df[df['name'] == selected_loc_name].iloc[0]
    
    is_open = loc['current_busy_level'] > 0
    status_color = "green" if is_open else "gray"
    status_text = "BEROPERASI" if is_open else "TUTUP / TANPA DATA LIVE"
    
    st.markdown(f"## 📍 {loc['name']} <span style='font-size:16px; color:{status_color}; border:1px solid {status_color}; padding:2px 8px; border-radius:5px;'>{status_text}</span>", unsafe_allow_html=True)

    # Tips Rekomendasi
    q_hour, q_perc = get_best_time(loc, curr_day)
    if q_hour:
        st.success(f"💡 **Rekomendasi:** Waktu tersepi hari ini pukul **{q_hour}:00** dengan kepadatan **{q_perc}%**.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Keramaian Sekarang", f"{int(loc['current_busy_level'])}%" if loc['has_data'] else "-")
    
    # Kolom 2: Sentimen Publik dengan Warna Dinamis
    sentiment = loc['sentiment_label']
    sentiment_color = {
        'Positif': '#09AB3B',
        'Negatif': '#FF4B4B',
        'Netral': '#FFC107'
    }.get(sentiment, '#000000')
    
    col2.markdown(f"""
        <p style='font-size:14px; color:rgba(49, 51, 63, 0.6); margin-bottom: 0px;'>Sentimen Publik</p>
        <p style='font-size:24px; font-weight:600; color:{sentiment_color}; margin-top: -5px;'>{sentiment}</p>
    """, unsafe_allow_html=True)
    
    col3.metric("Data Diupdate Per", loc['timestamp'])

    st.divider()

    g1, g2 = st.columns([2, 1])
    with g1:
        st.subheader(f"📊 Tren Keramaian ({curr_day})")
        chart_source = loc['popular_times'].get(curr_day, [])
        if chart_source:
            cdf = pd.DataFrame(chart_source)
            fig = px.bar(cdf, x='hour', y='percentage', labels={'hour':'Jam', 'percentage':'Ramai %'})
            bar_colors = ['#FF4B4B' if h == curr_hour else '#90CAF9' for h in cdf['hour']]
            fig.update_traces(marker_color=bar_colors)
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Grafik tren tidak tersedia untuk lokasi ini.")

    with g2:
        st.subheader("🤖 Analisis Singkat")
        st.info(loc.get('summary', 'Tidak ada ringkasan.'))
        
        st.write("**Topik Utama:**")
        topics = loc.get('topics', [])
        tags = "".join([f"<span style='background:#f0f2f6; padding:3px 8px; margin:2px; border-radius:10px;'>#{t}</span> " for t in topics])
        st.markdown(tags, unsafe_allow_html=True)

st.caption("Dashboard Monitoring v2.7 - Clean Hover & Dynamic Sentiment Colors")