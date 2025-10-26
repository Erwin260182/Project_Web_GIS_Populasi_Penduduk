# ======================================================
#  WebGIS Populasi – Flask + Folium (Versi Stabil)
#  Fitur:
#   - Filter: minimal populasi, keyword, dropdown nama
#   - Marker Cluster, Basemap Switcher, MiniMap, Fullscreen, Scale Bar
#   - Legend HTML + Badge jumlah titik (result_count)
#   - Tanpa Stamen (hindari error attribution) – pakai OSM, CartoDB, OpenTopoMap, ESRI
# ======================================================

from flask import Flask, render_template, request
import pandas as pd
import folium
from folium.plugins import MarkerCluster, MiniMap, Fullscreen
from pathlib import Path

# ------------------------------------------------------
# 1) Inisialisasi Aplikasi dan Data
# ------------------------------------------------------
app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "static" / "data_populasi.csv"

# Baca CSV (pastikan kolom: nama, lat, lon, populasi)
df = pd.read_csv(CSV_PATH)

required = {"nama", "lat", "lon", "populasi"}
missing = required - set(df.columns.str.lower())
if missing:
    raise ValueError(f"Kolom wajib hilang: {missing}. Pastikan ada: {required}")

# Tipe numerik
df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
df["populasi"] = pd.to_numeric(df["populasi"], errors="coerce")

# Daftar nama untuk dropdown
NAMES = sorted(df["nama"].dropna().astype(str).unique().tolist())

# ------------------------------------------------------
# 2) Layer dasar + Legend
# ------------------------------------------------------
def add_base_layers(m: folium.Map) -> None:
    """Basemap dengan attribution eksplisit agar bebas error."""

    # OpenStreetMap (preset aman)
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        control=True
    ).add_to(m)

    # CartoDB Positron (terang)
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        name="CartoDB Positron",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
             'contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains="abcd",
        max_zoom=20,
        control=True
    ).add_to(m)

    # CartoDB Dark (gelap)
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        name="CartoDB Dark",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
             'contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains="abcd",
        max_zoom=20,
        control=True
    ).add_to(m)

    # OpenTopoMap
    folium.TileLayer(
        tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        name="OpenTopoMap",
        attr='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
             'contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | '
             'Style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a>',
        subdomains="abc",
        max_zoom=17,
        control=True
    ).add_to(m)

    # ESRI World Imagery (citra)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        name="ESRI World Imagery",
        attr='Tiles &copy; Esri',
        max_zoom=19,
        control=True
    ).add_to(m)

    # ESRI World Topo
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        name="ESRI World Topo",
        attr='Tiles &copy; Esri',
        max_zoom=19,
        control=True
    ).add_to(m)


def add_legend(m: folium.Map) -> None:
    legend_html = """
    <div style="
        position: fixed; bottom: 20px; left: 20px; z-index: 9999;
        background: rgba(255,255,255,0.92); padding: 10px 12px;
        border-radius: 10px; box-shadow: 0 4px 16px rgba(0,0,0,.1);
        border: 1px solid rgba(0,0,0,.05); font-size: 14px;">
      <div style="font-weight: 700; margin-bottom: 6px;">Legenda</div>
      <div style="display:flex; align-items:center; gap:8px;">
        <span style="display:inline-block; width:12px; height:12px; border-radius:50%;
                     background:#2a81cb; border:2px solid #1f5d91;"></span>
        <span>Lokasi (Marker)</span>
      </div>
      <div style="margin-top:6px; font-size:12px; color:#6b7280;">
        Gunakan kontrol layer (kanan atas) untuk ganti basemap.
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

# ------------------------------------------------------
# 3) Bangun peta
# ------------------------------------------------------
def build_map(dframe: pd.DataFrame) -> tuple[str, int]:
    """Kembalikan (map_html, result_count)."""
    if len(dframe) > 0 and dframe["lat"].notna().any() and dframe["lon"].notna().any():
        center = [dframe["lat"].mean(), dframe["lon"].mean()]
    else:
        center = [-6.5, 107.0]

    m = folium.Map(location=center, zoom_start=8, control_scale=True)

    add_base_layers(m)
    MiniMap(toggle_display=True, position="bottomright").add_to(m)
    Fullscreen(position="topleft").add_to(m)

    cluster = MarkerCluster(name="Cluster Lokasi").add_to(m)
    count = 0
    for _, row in dframe.dropna(subset=["lat", "lon"]).iterrows():
        if pd.notna(row["populasi"]):
            popup_text = f"{row['nama']}<br>Populasi: {int(row['populasi']):,}"
        else:
            popup_text = f"{row['nama']}"
        folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=popup_text,
            tooltip=row["nama"]
        ).add_to(cluster)
        count += 1

    folium.LayerControl(collapsed=False).add_to(m)
    add_legend(m)

    return m._repr_html_(), count

# ------------------------------------------------------
# 4) Route Utama
# ------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def home():
    min_pop_str   = request.form.get("min_pop", "")
    keyword       = request.form.get("keyword", "")
    selected_name = request.form.get("name", "")

    dff = df.copy()

    if min_pop_str:
        try:
            min_pop = int(min_pop_str)
            dff = dff[dff["populasi"] >= min_pop]
        except ValueError:
            pass

    if keyword:
        dff = dff[dff["nama"].astype(str).str.contains(keyword, case=False, na=False)]

    if selected_name:
        dff = dff[dff["nama"].astype(str).str.casefold() == selected_name.casefold()]

    map_html, result_count = build_map(dff)

    return render_template(
        "home.html",
        map_html=map_html,
        min_pop=min_pop_str,
        keyword=keyword,
        names=NAMES,
        selected_name=selected_name,
        result_count=result_count,
    )

# ------------------------------------------------------
# 5) Run
# ------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
