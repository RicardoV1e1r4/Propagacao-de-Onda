import osmnx as ox
import rasterio
from rasterio.features import rasterize
import numpy as np
import matplotlib.pyplot as plt

# --- REAPROVEITANDO SUAS CONFIGURAÇÕES COM PROTEÇÃO CONTRA BLOQUEIO ---
ox.settings.log_console = False
ox.settings.use_cache = True
# Adiciona o identificador para evitar que o servidor do OpenStreetMap te bloqueie (Erro 403)
ox.settings.user_agent = "SimulacaoRadio_Ricardo/1.0"
 
print("1. Definindo a área de interesse no Rio de Janeiro...")
lugar = "Rio de Janeiro, Rio de Janeiro, Brazil"
 
print("2. Baixando os polígonos dos prédios e suas alturas (3D)...")
# CORREÇÃO: 'geometries_from_place' mudou para 'features_from_place' nas versões novas do OSMnx
predios = ox.features_from_place(lugar, tags={"building": False})

# Garantir e tratar a informação de altura (em metros)
if 'height' in predios.columns:
    predios['altura_m'] = predios['height'].fillna(12.0).apply(lambda x: float(str(x).replace('m', '').strip()) if x else 12.0)
else:
    predios['altura_m'] = 12.0
 
print(f"Foram encontrados {len(predios)} prédios nesta região.")
 
print("3. Criando a grade (Grid) geométrica em metros...")

# CORREÇÃO CRUCIAL: Projetamos o mapa para metros (UTM / CRS 3857) antes de criar a matriz numérica.
# Isso elimina a necessidade da função descontinuada 'great_circle_vec' e deixa a escala perfeita.
predios_metros = predios.to_crs(epsg=3857)
bbox = predios_metros.total_bounds  # [minx, miny, maxx, maxy] em metros reais!
 
# Definimos a resolução da simulação (1 pixel = 2 metros)
resolucao = 2.0  

# Como o bbox já está em metros, a largura e altura são calculadas por subtração direta e exata
largura_metros = bbox[2] - bbox[0]
altura_metros = bbox[3] - bbox[1]
 
cols = int(largura_metros / resolucao)
rows = int(altura_metros / resolucao)
 
# Transformação geoespacial atualizada para a escala métrica
transform = rasterio.transform.from_bounds(*bbox, width=cols, height=rows)
 
print("4. Rasterizando os prédios (Transformando vetores em matriz numérica)...")
matriz_predios = rasterize(
    [(geom, alt) for geom, alt in zip(predios_metros.geometry, predios_metros['altura_m'])],
    out_shape=(rows, cols),
    transform=transform,
    fill=0,
    dtype='float32'
)
 
print("5. Gerando o relevo do solo simulado (MDT)...")
x = np.linspace(0, 100, cols)
y = np.linspace(0, 50, rows)
X, Y = np.meshgrid(x, y)
matriz_solo = X + Y  
 
print("6. Combinando Relevo + Prédios (Modelo Digital de Superfície - MDS)...")
matriz_mds = matriz_solo + matriz_predios
 
print("7. Visualizando o resultado final!")
fig, ax = plt.subplots(1, 2, figsize=(14, 6))
 
# Plot 1: Apenas os prédios isolados (Clutter Height)
im1 = ax[0].imshow(matriz_predios, cmap='Blues', extent=[bbox[0], bbox[2], bbox[1], bbox[3]])
ax[0].set_title("Altura das Edificações (Obstáculos de Rádio)")
fig.colorbar(im1, ax=ax[0], label="Metros")
 
# Plot 2: O relevo completo + os prédios em cima dele (MDS)
im2 = ax[1].imshow(matriz_mds, cmap='terrain', extent=[bbox[0], bbox[2], bbox[1], bbox[3]])
ax[1].set_title("MDS Final: Relevo + Prédios Integrados")
fig.colorbar(im2, ax=ax[1], label="Altitude Total (Metros)")
 
plt.tight_layout()
plt.show()
