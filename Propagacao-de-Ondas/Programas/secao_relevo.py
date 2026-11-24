
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from pyproj import Transformer
from rasterio.windows import from_bounds

arquivo = "Arquivos dos relevos/rasters_COP30/output_hh - Copia.tif"

# Limites geográficos do recorte
oeste = -43.4065
leste = -43.1607
sul = -23.0104
norte = -22.8851

# Coordenadas geográficas dos extremos da seção
lon_inicio, lat_inicio = -43.2107, -22.9238 # -43.189, -22.909
lon_fim, lat_fim = -43.1733, -22.9353 # -43.175, -22.899

# Transformadores entre coordenadas geográficas e UTM
para_utm = Transformer.from_crs(
    "EPSG:4326", "EPSG:31983", always_xy=True
)
para_geo = Transformer.from_crs(
    "EPSG:31983", "EPSG:4326", always_xy=True
)

# Converter extremos para coordenadas métricas
x0, y0 = para_utm.transform(lon_inicio, lat_inicio)
x1, y1 = para_utm.transform(lon_fim, lat_fim)

# Distância total da seção em metros
distancia_total = np.hypot(x1 - x0, y1 - y0)

# Número de pontos amostrados ao longo da seção
n = max(2, int(distancia_total / 10) + 1)

# Gerar pontos igualmente espaçados em UTM
x = np.linspace(x0, x1, n)
y = np.linspace(y0, y1, n)

# Converter os pontos para longitude e latitude
lon, lat = para_geo.transform(x, y)

# Amostrar as elevações no TIFF
with rasterio.open(arquivo) as src:
    pontos = list(zip(lon, lat))
    amostras = list(src.sample(pontos, masked=True))

    elevacao = np.ma.array(
        [p[0] for p in amostras],
        mask=[np.ma.is_masked(p[0]) for p in amostras]
    )

    # Criar janela correspondente à área desejada
    janela = from_bounds(
        oeste, sul, leste, norte,
        transform=src.transform
    ).round_offsets().round_lengths()

    # Ler somente a região selecionada
    relevo = src.read(1, window=janela, masked=True)

    # Transformação espacial do recorte
    transform = src.window_transform(janela)

    # Coordenadas dos limites do recorte
    x_min = transform.c
    y_max = transform.f
    x_max = x_min + relevo.shape[1] * transform.a
    y_min = y_max + relevo.shape[0] * transform.e

# Distância acumulada em metros
distancia = np.linspace(0, distancia_total, n)

# Plotar perfil de elevação
plt.figure(figsize=(12, 5))

plt.plot(distancia, elevacao, linewidth=1.5)
plt.fill_between(
    distancia, elevacao, np.min(elevacao),
    alpha=0.25
)

plt.xlabel("Distância (m)")
plt.ylabel("Elevação (m)")
plt.title("Perfil de elevação do terreno")
plt.grid(True)
plt.tight_layout()

#----------------------------------------------

# Execute após o código do recorte e do perfil

plt.figure(figsize=(10, 7))

plt.imshow(
    relevo,
    extent=[x_min, x_max, y_min, y_max],
    # extent=[x_0, x_1, y_0, y_1],
    origin="upper",
    cmap="terrain",
    aspect="auto"
)

plt.plot(
    [lon_inicio, lon_fim],
    [lat_inicio, lat_fim],
    color="red",
    linewidth=2,
    label="Seção transversal"
)

plt.scatter(
    [lon_inicio, lon_fim],
    [lat_inicio, lat_fim],
    color="red",
    s=40
)

plt.colorbar(label="Elevação (m)")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.title("Localização da seção transversal")
plt.legend()
plt.tight_layout()

plt.show()