# -*- coding: utf-8 -*-
"""
Created on Sat Sep 26 21:27:47 2026

@author: Ricardo Alexandre
"""

import osmnx as ox
import folium
from folium.plugins import HeatMap
import pandas as pd

print("1. Baixando edifícios de Niterói (teste rápido)...")

# Definindo uma área menor para testar sem travar
place_query = "Niterói, Rio de Janeiro, Brazil"

# Baixa as pegadas de edifícios (footprints)
gdf_buildings = ox.features_from_place(place_query, tags={'building': True})
print(f"Sucesso! {len(gdf_buildings)} edifícios encontrados.")

print("2. Processando dados de altura (2.5D)...")

# Cria uma coluna unificada de "Peso da Altura"
def calcular_peso_altura(row):
    if 'height' in row and pd.notnull(row['height']):
        try:
            return float(str(row['height']).replace('m', '').strip())
        except ValueError:
            pass
    if 'building:levels' in row and pd.notnull(row['building:levels']):
        try:
            return float(row['building:levels']) * 3.0
        except ValueError:
            pass
    return 3.5

gdf_buildings['altura_estimada'] = gdf_buildings.apply(calcular_peso_altura, axis=1)

# --- CORREÇÃO DO CENTROID ---
# Projetamos temporariamente para metros (CRS 3857) para calcular o centroide exato,
# e depois convertemos de volta para o sistema geográfico de Latitude/Longitude (CRS 4326)
gdf_buildings_projetado = gdf_buildings.to_crs(epsg=3857)
centroids_projetados = gdf_buildings_projetado.geometry.centroid
centroids_geograficos = centroids_projetados.to_crs(epsg=4326)

gdf_buildings['lat'] = centroids_geograficos.y
gdf_buildings['lon'] = centroids_geograficos.x

# Prepara a lista no formato aceito pelo Folium: [[lat, lon, peso/altura]]
heat_data = gdf_buildings[['lat', 'lon', 'altura_estimada']].values.tolist()

print("3. Renderizando o mapa de calor interativo...")

# Centraliza o mapa inicial em Niterói / RJ
mapa_rj = folium.Map(
    location=[-22.8833, -43.1167], 
    zoom_start=12, 
    # --- CORREÇÃO DO TILES/BACKGROUND ---
    # Mudamos para o "OpenStreetMap", que é 100% gratuito e não exige chave de API
    tiles="OpenStreetMap" 
)

# Adiciona a camada do mapa de calor com base na densidade de altura 2.5D
HeatMap(
    data=heat_data,
    radius=15,          
    blur=10,            
    max_zoom=13,        
    min_opacity=0.4
).add_to(mapa_rj)

# Salva o mapa no mesmo diretório do seu script
nome_arquivo = "mapa_calor_25d_rj.html"
mapa_rj.save(nome_arquivo)

print(f"\nPronto! O mapa limpo e corrigido foi salvo como '{nome_arquivo}'.")

"""
import osmnx as ox
import rasterio
from rasterio.features import rasterize
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import box
 
# Configuração do OSMnx
ox.settings.log_console = False
ox.settings.use_cache = True
 
print("1. Definindo a área de interesse no Rio de Janeiro...")
# Você pode buscar por "Copacabana, Rio de Janeiro", "Centro, Rio de Janeiro", etc.
lugar = "Copacabana, Rio de Janeiro, Brazil"
 
print("2. Baixando os polígonos dos prédios e suas alturas (3D)...")
# Baixa todas as construções (buildings) da região demarcada
predios = ox.geometries_from_place(lugar, tags={"building": True})
 
# Filtrar e garantir que temos a informação de altura (em metros)
# Se o prédio não tiver altura cadastrada no OSM, assumimos um padrão de 12 metros (~3 andares)
if 'height' in predios.columns:
    predios['altura_m'] = predios['height'].fillna(12.0).apply(lambda x: float(str(x).replace('m', '').strip()) if x else 12.0)
else:
    predios['altura_m'] = 12.0
 
print(f"Foram encontrados {len(predios)} prédios nesta região.")
 
print("3. Criando a grade (Grid) para a simulação...")
# Pegamos os limites geográficos (Bounding Box) do bairro mapeado
bbox = predios.total_bounds  # [minx, miny, maxx, maxy]
geometria_area = box(*bbox)
 
# Definimos a resolução do nosso mapa de simulação (Ex: 1 pixel = 2 metros)
resolucao = 2.0  # metros por pixel
largura_metros = ox.distance.great_circle_vec(bbox[1], bbox[0], bbox[1], bbox[2])
altura_metros = ox.distance.great_circle_vec(bbox[1], bbox[0], bbox[3], bbox[0])
 
cols = int(largura_metros / resolucao)
rows = int(altura_metros / resolucao)
 
# Transformação geoespacial para mapear pixels em coordenadas reais
transform = rasterio.transform.from_bounds(*bbox, width=cols, height=rows)
 
print("4. Rasterizando os prédios (Transformando vetores em matriz numérica)...")
# Criamos uma matriz onde o fundo é 0 e os pixels onde há prédios recebem a altura deles
matriz_predios = rasterize(
    [(geom, alt) for geom, alt in zip(predios.geometry, predios['altura_m'])],
    out_shape=(rows, cols),
    transform=transform,
    fill=0,
    dtype='float32'
)
 
print("5. Gerando o relevo do solo simulado (MDT)...")
# DICA: Para produção, aqui você carregaria o arquivo .tif gerado pelo 'elevation' ou prefeitura.
# Para o código rodar direto sem depender de chaves de API externas, criamos um gradiente topográfico simples.
x = np.linspace(0, 100, cols)
y = np.linspace(0, 50, rows)
X, Y = np.meshgrid(x, y)
matriz_solo = X + Y  # Simula uma inclinação suave típica de subida de morro no Rio
 
print("6. Combinando Relevo + Prédios (Modelo Digital de Superfície - MDS)...")
# O relevo real que a onda de rádio enxerga é o Solo SOMADO com a Altura dos Prédios
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
"""
 