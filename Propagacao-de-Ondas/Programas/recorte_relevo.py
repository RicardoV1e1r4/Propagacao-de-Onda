
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from rasterio.windows import from_bounds

# Arquivo de entrada
arquivo = "Arquivos dos relevos/rasters_COP30/output_hh - Copia.tif"

# Limites geográficos do recorte
oeste = -43.4065 # -43.189
leste = -43.1607 # -43.175
sul = -23.0104 # -22.909
norte = -22.8851 # -22.899

with rasterio.open(arquivo) as src:
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

# Plotar o recorte
plt.figure(figsize=(10, 7))

imagem = plt.imshow(
    relevo,
    extent=[x_min, x_max, y_min, y_max],
    origin="upper",
    cmap="terrain",
    aspect="auto"
)

plt.colorbar(imagem, label="Elevação (m)")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.title("Recorte do relevo do terreno")
plt.tight_layout()
plt.show()