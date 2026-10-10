import numpy as np
import matplotlib.pyplot as plt

Pt = 1
Gt = 10
Gr = 1e-12
f = 1800e6
r = 0.1e3
c = 3e8
pi = np.pi

# 1. Criar a malha de pontos (X e Y) vista de cima
x = np.linspace(-r, r, 800)
y = np.linspace(-r, r, 800)
X, Y = np.meshgrid(x, y)

# 2. Definir a função da parábola convexa (Z) estendida para 2D
# Z = -(X**2 + Y**2) + 6
Pr = 10*np.log(Pt * Gt * Gr * ((c/f)/(4*pi*(np.sqrt(X**2 + Y**2) + 0.001)))**2)

# 3. Configurar o gráfico
plt.figure(figsize=(8, 6))

# Usar 'contourf' para criar os contornos de cores preenchidos
# O mapa de cores 'viridis' ou 'plasma' é ótimo para intensidade de altura
grafico = plt.contourf(X, Y, Pr, levels=50, cmap='plasma')

# Adicionar uma barra de cores lateral para servir de legenda da altura (Z)
barra_cores = plt.colorbar(grafico)
barra_cores.set_label('Potência ($dB$)', fontsize=12)

# Customizações do mapa
plt.title('Modelo de espaço livre', fontsize=14)
# plt.title('Visão de Cima de uma Parábola Convexa: $Z = -(x^2 + y^2) + 6$', fontsize=14)
plt.xlabel('Eixo X', fontsize=12)
plt.ylabel('Eixo Y', fontsize=12)
plt.grid(True, linestyle='--', alpha=0.5)

# Exibir a imagem
plt.show()
