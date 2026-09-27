import osmnx as ox
import rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# CONFIGURAÇÕES
# ============================================================

ox.settings.log_console = True
ox.settings.use_cache = True

ox.settings.http_user_agent = "SimulacaoRadio_Ricardo/2.0"

ox.settings.overpass_url = "https://overpass.private.coffee/api"

ox.settings.requests_timeout = 180

ox.settings.overpass_rate_limit = False

# Bounding box - WGS84
oeste = -43.189
sul   = -22.909
leste = -43.175
norte = -22.899

# Resolução espacial
resolucao = 2.0  # metros

# Arquivo do MDT
arquivo_mdt = "mdt.tif"

# ============================================================
# 1. DOWNLOAD DOS PRÉDIOS
# ============================================================

print("1. Baixando edifícios do OpenStreetMap...")

# OSMnx 2.x:
# (west, south, east, north)

coord_tupla = (oeste, sul, leste, norte)

predios = ox.features_from_bbox(
    bbox=coord_tupla,
    tags={"building": True}
)

print(f"Prédios encontrados: {len(predios)}")

# ============================================================
# 2. DETERMINAÇÃO DAS ALTURAS
# ============================================================

def obter_altura(row):
    # ----------------------------------
    # Primeiro: altura explícita
    # ----------------------------------

    if row.get("height") is not None:
        try:
            valor = str(row["height"]).lower()
            valor = valor.replace("m", "")
            valor = valor.strip()

            return float(valor)

        except (ValueError, TypeError):
            pass


    # ----------------------------------
    # Segundo: número de pavimentos
    # ----------------------------------

    if row.get("building:levels") is not None:
        try:
            niveis = float(row["building:levels"])

            # aproximadamente 3 m por pavimento
            return niveis * 3.0

        except (ValueError, TypeError):
            pass


    # ----------------------------------
    # Terceiro: valor padrão
    # ----------------------------------

    return 12.0


predios["altura_m"] = predios.apply(obter_altura, axis=1)

print(
    f"Altura média estimada: "
    f"{predios['altura_m'].mean():.2f} m"
)


# ============================================================
# 3. PROJEÇÃO MÉTRICA
# ============================================================

print("2. Projetando para SIRGAS 2000 / UTM 23S...")

predios_metros = predios.to_crs(epsg=31983)

bbox_metros = predios_metros.total_bounds

xmin, ymin, xmax, ymax = bbox_metros

largura_metros = xmax - xmin
altura_metros  = ymax - ymin

cols = int(np.ceil(largura_metros / resolucao))
rows = int(np.ceil(altura_metros / resolucao))

transform = from_bounds(
    xmin,
    ymin,
    xmax,
    ymax,
    cols,
    rows
)

print(f"Área: {largura_metros:.1f} × {altura_metros:.1f} m")
print(f"Grade: {cols} × {rows}")


# ============================================================
# 4. RASTERIZAÇÃO DOS PRÉDIOS
# ============================================================

print("3. Rasterizando prédios...")

matriz_predios = rasterize(
    [
        (geom, altura)
        for geom, altura
        in zip(
            predios_metros.geometry,
            predios_metros["altura_m"]
        )
        if geom is not None and not geom.is_empty
    ],
    out_shape=(rows, cols),
    transform=transform,
    fill=0,
    dtype="float32"
)


# ============================================================
# 5. CARREGAMENTO DO MDT REAL
# ============================================================

print("4. Carregando MDT real...")

matriz_solo = np.zeros(
    (rows, cols),
    dtype="float32"
)

with rasterio.open(arquivo_mdt) as src:
    reproject(
        source=rasterio.band(src, 1),

        destination=matriz_solo,

        src_transform=src.transform,
        src_crs=src.crs,

        dst_transform=transform,
        dst_crs="EPSG:31983",

        resampling=Resampling.bilinear
    )


# ============================================================
# 6. MDS = TERRENO + PRÉDIOS
# ============================================================

print("5. Gerando MDS...")

matriz_mds = matriz_solo + matriz_predios


# ============================================================
# 7. VISUALIZAÇÃO
# ============================================================

print("6. Gerando gráficos...")

extent = [
    xmin,
    xmax,
    ymin,
    ymax
]

fig, ax = plt.subplots(
    1,
    2,
    figsize=(14, 6)
)


# Prédios
im1 = ax[0].imshow(
    matriz_predios,
    cmap="Blues",
    extent=extent,
    origin="upper"
)

ax[0].set_title("Altura dos prédios")
ax[0].set_xlabel("Easting (m)")
ax[0].set_ylabel("Northing (m)")

fig.colorbar(
    im1,
    ax=ax[0],
    label="Altura (m)"
)


# MDS
im2 = ax[1].imshow(
    matriz_mds,
    cmap="terrain",
    extent=extent,
    origin="upper"
)

ax[1].set_title("MDS: terreno + prédios")
ax[1].set_xlabel("Easting (m)")
ax[1].set_ylabel("Northing (m)")
fig.colorbar(
    im2,
    ax=ax[1],
    label="Altitude (m)"
)

plt.tight_layout()
plt.show()
