# -*- coding: utf-8 -*-
"""
Created on Sun Sep 27 15:00:03 2026

@author: Ricardo Alexandre
"""

import rasterio
from rasterio.plot import show
import matplotlib.pyplot as plt

# 1. Caminho para o seu arquivo TIFF de relevo
caminho_arquivo = "D:/Documentos/Engenharia/8º Período/Propagação de Ondas/Programas feitos pelo Ricardo/Arquivos dos relevos/rasters_COP30_02/output_hh.tif"

# 2. Abrir o arquivo usando o Rasterio
with rasterio.open(caminho_arquivo) as src:
    # Ler a primeira banda (geralmente arquivos de relevo possuem apenas 1 banda com as altitudes)
    dados_relevo = src.read(1)
    
    # Mostrar metadados básicos no terminal (Opcional)
    print(f"Dimensões do terreno: {src.width}x{src.height} pixels")
    print(f"Sistema de Coordenadas (CRS): {src.crs}")
    print(f"Altitude Mínima: {dados_relevo.min()}m")
    print(f"Altitude Máxima: {dados_relevo.max()}m")

# 3. Imprimir/Visualizar o relevo na tela
plt.figure(figsize=(10, 8))
# Usamos o mapa de cores 'terrain' que é ideal para topografia
img = plt.imshow(dados_relevo, cmap='terrain')

# Adiciona uma barra lateral para indicar a escala de altitude
plt.colorbar(img, label='Altitude (metros)')

plt.title('Visualização do Relevo do Terreno')
plt.xlabel('Colunas (Pixels)')
plt.ylabel('Linhas (Pixels)')

# Exibe a janela com o gráfico impresso
plt.show()
