import osmnx as ox
import rasterio
from rasterio.features import rasterize
import numpy as np
import matplotlib.pyplot as plt

# Evita bloqueios de API (Erro 403)
ox.settings.log_console = False
ox.settings.use_cache = True
ox.settings.user_agent = "SimulacaoRadio_Ricardo/2.0"

# =============================================================================
# PASSO 1: DEFINA SUAS COORDENADAS PERSONALIZADAS (WGS84)
# =============================================================================
# DICA: Você pode pegar essas coordenadas facilmente desenhando um retângulo no site bboxfinder.com
# Exemplo atual: Um recorte cobrindo o Centro do Rio de Janeiro

oeste = -43.189
sul   = -22.909
leste = -43.175
norte = -22.899

print("1. Baixando os edifícios dentro da sua caixa delimitadora...")
# Baixa as geometrias diretamente pelas coordenadas limites fornecidas
coord_tupla = (oeste, sul, leste, norte)
predios = ox.features_from_bbox(coord_tupla, tags={"building": True})

# Tratamento padrão de altura 2.5D
if 'height' in predios.columns:
    predios['altura_m'] = predios['height'].fillna(12.0).apply(lambda x: float(str(x).replace('m', '').strip()) if x else 12.0)
else:
    predios['altura_m'] = 12.0

print(f"Foram encontrados {len(predios)} prédios na área delimitada.")

# =============================================================================
# PASSO 2: CRIAÇÃO DA GRADE EM METROS
# =============================================================================
print("2. Projetando a área para coordenadas métricas...")
predios_metros = predios.to_crs(epsg=3857)
bbox = predios_metros.total_bounds  # [minx, miny, maxx, maxy] em metros

# Resolução da grade (2 metros por pixel)
resolucao = 2.0  
largura_metros = bbox[2] - bbox[0]
altura_metros = bbox[3] - bbox[1]

cols = int(largura_metros / resolucao)
rows = int(altura_metros / resolucao)

transform = rasterio.transform.from_bounds(*bbox, width=cols, height=rows)

# =============================================================================
# PASSO 3: RASTERIZAÇÃO DOS PRÉDIOS
# =============================================================================
print("3. Gerando matriz numérica dos obstáculos (Prédios)...")
matriz_predios = rasterize(
    [(geom, alt) for geom, alt in zip(predios_metros.geometry, predios_metros['altura_m'])],
    out_shape=(rows, cols),
    transform=transform,
    fill=0,
    dtype='float32'
)

# =============================================================================
# PASSO 4: ADICIONANDO O RELEVO (MDT)
# =============================================================================
# Mude para True quando tiver o arquivo .tif do relevo real na mesma pasta!
USAR_MDT_REAL = False  

if USAR_MDT_REAL:
    print("4. Carregando relevo real a partir de arquivo GeoTIFF externo...")
    # Caminho do seu arquivo baixado (Ex: TOPODATA/INPE ou SRTM)
    with rasterio.open("seu_arquivo_relevo.tif") as src:
        # Lê o arquivo e força o redimensionamento exato para a mesma grade dos prédios
        matriz_solo = src.read(1, out_shape=(rows, cols), resampling=rasterio.enums.Resampling.bilinear)
else:
    print("4. Gerando relevo simulado matemático (Padrão)...")
    # Mantém a simulação matemática caso ainda não tenha o arquivo físico
    x = np.linspace(0, 100, cols)
    y = np.linspace(0, 50, rows)
    X, Y = np.meshgrid(x, y)
    matriz_solo = X + Y

# =============================================================================
# PASSO 5: INTEGRAÇÃO FINAL (MDS) E PLOT
# =============================================================================
print("5. Combinando Relevo + Prédios (MDS)...")
matriz_mds = matriz_solo + matriz_predios

print("6. Renderizando gráficos comparativos...")
fig, ax = plt.subplots(1, 2, figsize=(14, 6))

# Plot 1: Edificações isoladas
im1 = ax[0].imshow(matriz_predios, cmap='Blues', extent=[bbox[0], bbox[2], bbox[1], bbox[3]])
ax[0].set_title("Apenas Prédios (Obstáculos Isolados)")
fig.colorbar(im1, ax=ax[0], label="Altura do Prédio (m)")

# Plot 2: Modelo Digital de Superfície Combinado
im2 = ax[1].imshow(matriz_mds, cmap='terrain', extent=[bbox[0], bbox[2], bbox[1], bbox[3]])
ax[1].set_title("MDS Integrado (Terreno + Prédios)")
fig.colorbar(im2, ax=ax[1], label="Altitude Absoluta (m)")

plt.tight_layout()
plt.show()
