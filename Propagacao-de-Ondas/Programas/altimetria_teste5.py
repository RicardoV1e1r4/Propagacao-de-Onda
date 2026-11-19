# -*- coding: utf-8 -*-
"""
Altimetria - teste 5

Terreno (MDT, 30 m) + edifícios do OpenStreetMap, visualizados como mapa de
calor no matplotlib.

Fontes de terreno, em ordem de preferência:
    1. ANADEM já salvo em PASTA_ANADEM (recortes de execuções anteriores)
    2. ANADEM baixado da internet (só o pedaço que cobre a área)
    3. Copernicus GLO-30 já baixado (ARQUIVO_COP30) - dado de 2011-2015

ANADEM: UFRGS/ANA, 30 m, Copernicus corrigido para remover a vegetação
(Laipelt et al., Remote Sensing 16(13), 2321, 2024).

@author: Ricardo Alexandre
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds

# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Área de interesse (WGS84, graus) - padrão: Centro do Rio
OESTE = -43.189
SUL   = -22.909
LESTE = -43.175
NORTE = -22.899

# Resolução da grade de saída (metros por pixel).
# O terreno tem 30 m; a grade mais fina serve para os edifícios aparecerem.
# Use 30.0 para ver o terreno na resolução original.
RESOLUCAO = 2.0

# True  -> terreno + edifícios (MDS)
# False -> somente terreno (MDT)
MOSTRAR_EDIFICIOS = True

# Altura padrão para prédios sem 'height' nem 'building:levels' no OSM
ALTURA_PADRAO = 12.0

# Servidores Overpass (OpenStreetMap), tentados em ordem até um responder
SERVIDORES_OVERPASS = [
    "https://overpass-api.de/api",
    "https://overpass.kumi.systems/api",
    "https://overpass.private.coffee/api",
]
TIMEOUT_OVERPASS = 60  # segundos por servidor
RODADAS_OVERPASS = 4   # quantas vezes tentar a lista inteira
ESPERA_INICIAL   = 15  # segundos de espera após a 1ª rodada (dobra a cada rodada)

# Pastas/arquivos de relevo (relativos à pasta deste script)
PASTA_SCRIPT  = Path(__file__).resolve().parent
PASTA_ANADEM  = PASTA_SCRIPT / "Arquivos dos relevos" / "ANADEM"
ARQUIVO_COP30 = PASTA_SCRIPT / "Arquivos dos relevos" / "rasters_COP30_02" / "output_hh.tif"

# Tiles do ANADEM (o código do tile, ex. "23K" para o Rio, é calculado pela área)
URL_ANADEM = "https://metadados.snirh.gov.br/files/anadem_v1_tiles/anadem_v1_{tile}.tif"

# Sistema métrico de saída: SIRGAS 2000 / UTM 23S
CRS_SAIDA = "EPSG:31983"

# Fração máxima da área que pode ficar sem dado para aceitar uma fonte
MAX_FRACAO_SEM_DADO = 0.01


# ============================================================
# 1. GRADE DE SAÍDA (em metros)
# ============================================================

def criar_grade():
    xmin, ymin, xmax, ymax = transform_bounds(
        "EPSG:4326", CRS_SAIDA, OESTE, SUL, LESTE, NORTE
    )
    cols = int(np.ceil((xmax - xmin) / RESOLUCAO))
    rows = int(np.ceil((ymax - ymin) / RESOLUCAO))
    transform = from_origin(xmin, ymax, RESOLUCAO, RESOLUCAO)
    extent = [xmin, xmin + cols * RESOLUCAO, ymax - rows * RESOLUCAO, ymax]
    return transform, rows, cols, extent


# ============================================================
# 2. TERRENO (MDT)
# ============================================================

def ler_recorte(src, margem_px=3):
    """
    Lê só a janela do raster que cobre a área de interesse (+ margem).
    Retorna (array com NaN no nodata, transform da janela) ou (None, None).
    """
    o, s, l, n = transform_bounds("EPSG:4326", src.crs, OESTE, SUL, LESTE, NORTE)
    janela = from_bounds(o, s, l, n, transform=src.transform)
    janela = Window(
        janela.col_off - margem_px, janela.row_off - margem_px,
        janela.width + 2 * margem_px, janela.height + 2 * margem_px,
    ).round_offsets().round_lengths()
    try:
        janela = janela.intersection(Window(0, 0, src.width, src.height))
    except rasterio.errors.WindowError:
        return None, None  # o raster não cobre a área

    dados = src.read(1, window=janela, masked=True).astype("float32")
    return dados.filled(np.nan), src.window_transform(janela)


def resolucao_metros(src):
    return src.res[0] * 111_320 if src.crs.is_geographic else src.res[0]


def montar_terreno(arquivos, transform, rows, cols):
    """Reprojeta cada arquivo na grade de saída e junta tudo (mosaico)."""
    terreno = np.full((rows, cols), np.nan, dtype="float32")
    usou_algum = False

    for arq in arquivos:
        with rasterio.open(arq) as src:
            if src.crs is None:
                continue
            dados, transf_janela = ler_recorte(src)
            if dados is None:
                continue
            usou_algum = True

            tile = np.full((rows, cols), np.nan, dtype="float32")
            reproject(
                source=dados,
                destination=tile,
                src_transform=transf_janela,
                src_crs=src.crs,
                src_nodata=np.nan,
                dst_transform=transform,
                dst_crs=CRS_SAIDA,
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
            vazio = np.isnan(terreno)
            terreno[vazio] = tile[vazio]

    return terreno if usou_algum else None


def tiles_mgrs():
    """Códigos MGRS (zona UTM + banda de latitude) que cobrem a área."""
    bandas = "CDEFGHJKLMNPQRSTUVWX"
    tiles = set()
    for lon in (OESTE, LESTE):
        for lat in (SUL, NORTE):
            zona = int((lon + 180) // 6) + 1
            banda = bandas[int((lat + 80) // 8)]
            tiles.add(f"{zona}{banda}")
    return sorted(tiles)


def baixar_anadem():
    """
    Lê pela internet só o recorte necessário de cada tile do ANADEM e salva
    em PASTA_ANADEM. Retorna a lista de arquivos salvos.
    """
    PASTA_ANADEM.mkdir(parents=True, exist_ok=True)
    salvos = []
    env = rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        GDAL_HTTP_TIMEOUT=120,
        GDAL_HTTP_MAX_RETRY=3,
    )
    with env:
        for tile in tiles_mgrs():
            url = URL_ANADEM.format(tile=tile)
            print(f"   Lendo recorte do tile {tile}: {url}")
            try:
                with rasterio.open("/vsicurl/" + url) as src:
                    dados, transf_janela = ler_recorte(src, margem_px=10)
                    if dados is None:
                        continue
                    perfil = {
                        "driver": "GTiff", "dtype": "float32", "count": 1,
                        "width": dados.shape[1], "height": dados.shape[0],
                        "crs": src.crs, "transform": transf_janela,
                        "nodata": np.nan, "compress": "deflate",
                    }
            except rasterio.errors.RasterioIOError as erro:
                print(f"   Falha ao acessar o tile {tile}: {erro}")
                continue

            nome = (f"anadem_{tile}_{OESTE:.4f}_{SUL:.4f}_{LESTE:.4f}_{NORTE:.4f}.tif"
                    .replace("-", "m"))
            destino = PASTA_ANADEM / nome
            with rasterio.open(destino, "w", **perfil) as dst:
                dst.write(dados, 1)
            print(f"   Recorte salvo em: {destino}")
            salvos.append(destino)
    return salvos


def tentar_fonte(nome, arquivos, transform, rows, cols):
    if not arquivos:
        return None
    terreno = montar_terreno(arquivos, transform, rows, cols)
    if terreno is None:
        print(f"   - {nome}: arquivos não cobrem a área.")
        return None
    fracao_vazia = np.isnan(terreno).mean()
    if fracao_vazia > MAX_FRACAO_SEM_DADO:
        print(f"   - {nome}: cobre só {100 * (1 - fracao_vazia):.1f}% da área, ignorado.")
        return None
    return terreno


def carregar_terreno(transform, rows, cols):
    # 1. ANADEM já salvo
    terreno = tentar_fonte("ANADEM (salvo)", sorted(PASTA_ANADEM.glob("*.tif")),
                           transform, rows, cols)
    if terreno is not None:
        print("   -> Usando ANADEM (30 m) já salvo em disco.")
        return terreno, "ANADEM 30 m"

    # 2. ANADEM pela internet
    print("   Recorte do ANADEM não encontrado; baixando...")
    terreno = tentar_fonte("ANADEM (internet)", baixar_anadem(), transform, rows, cols)
    if terreno is not None:
        print("   -> Usando ANADEM (30 m) recém-baixado.")
        return terreno, "ANADEM 30 m"

    # 3. Copernicus local
    if ARQUIVO_COP30.exists():
        terreno = tentar_fonte("Copernicus", [ARQUIVO_COP30], transform, rows, cols)
        if terreno is not None:
            print("   -> Usando Copernicus GLO-30 local.")
            print("   AVISO: dado de 2011-2015 e é um MDS (já inclui vegetação e "
                  "prédios antigos); somado aos edifícios do OSM, as alturas ficam exageradas.")
            return terreno, "Copernicus GLO-30 (2011-2015)"

    print("\nNenhuma fonte de terreno cobre a área escolhida.")
    print(f"  Baixe o tile do ANADEM em https://hge-iph.github.io/anadem/ "
          f"(tile(s) {', '.join(tiles_mgrs())}) e coloque em:\n    {PASTA_ANADEM}")
    sys.exit(1)


# ============================================================
# 3. EDIFÍCIOS (OpenStreetMap)
# ============================================================

def para_float(valor):
    if valor is None or pd.isna(valor):
        return None
    try:
        texto = str(valor).lower().replace("m", "").replace(",", ".").strip()
        numero = float(texto.split(";")[0])
        return numero if np.isfinite(numero) and numero > 0 else None
    except ValueError:
        return None


def obter_altura(row):
    """Retorna (altura_m, tem_altura_real)."""
    altura = para_float(row.get("height"))
    if altura is not None:
        return altura, True
    niveis = para_float(row.get("building:levels"))
    if niveis is not None:
        return niveis * 3.0, True  # ~3 m por pavimento
    return ALTURA_PADRAO, False


def carregar_edificios(transform, rows, cols):
    import time
    import osmnx as ox
    import requests

    ox.settings.log_console = False
    ox.settings.use_cache = True
    ox.settings.http_user_agent = "SimulacaoRadio_Ricardo/2.0"
    ox.settings.requests_timeout = TIMEOUT_OVERPASS
    ox.settings.overpass_rate_limit = False  # nem todo servidor tem /status

    sem_predios = np.zeros((rows, cols), dtype="float32")
    predios = None
    espera = ESPERA_INICIAL

    # Servidores públicos costumam ficar lotados (erro 502/504 ou timeout):
    # tenta todos, espera, e tenta de novo dobrando a espera a cada rodada.
    for rodada in range(1, RODADAS_OVERPASS + 1):
        for servidor in SERVIDORES_OVERPASS:
            ox.settings.overpass_url = servidor
            print(f"   [rodada {rodada}] Consultando {servidor} ...")
            try:
                predios = ox.features_from_bbox(
                    bbox=(OESTE, SUL, LESTE, NORTE),  # OSMnx 2.x: (oeste, sul, leste, norte)
                    tags={"building": True},
                )
                break
            except ox._errors.InsufficientResponseError:
                print("   Nenhum edifício encontrado na área.")
                return sem_predios
            except ox._errors.ResponseStatusCodeError as erro:
                print(f"   Falhou: {str(erro).splitlines()[0][:90]}")
            except requests.exceptions.RequestException as erro:
                print(f"   Falhou ({type(erro).__name__}).")
        if predios is not None:
            break
        if rodada < RODADAS_OVERPASS:
            print(f"   Servidores ocupados; aguardando {espera} s para tentar de novo...")
            time.sleep(espera)
            espera *= 2

    if predios is None:
        print("   AVISO: nenhum servidor Overpass respondeu. "
              "O mapa será mostrado só com o terreno.")
        return sem_predios

    predios = predios[predios.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

    alturas = predios.apply(obter_altura, axis=1, result_type="expand")
    predios = predios.assign(altura_m=alturas[0], altura_real=alturas[1])

    n_real = int(predios["altura_real"].sum())
    print(f"   {len(predios)} edifícios baixados; {n_real} com altura cadastrada, "
          f"{len(predios) - n_real} com altura padrão de {ALTURA_PADRAO} m.")

    predios = predios.to_crs(CRS_SAIDA)

    return rasterize(
        [(g, h) for g, h in zip(predios.geometry, predios["altura_m"])
         if g is not None and not g.is_empty],
        out_shape=(rows, cols),
        transform=transform,
        fill=0,
        dtype="float32",
    )


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():
    print("1. Criando a grade de saída...")
    transform, rows, cols, extent = criar_grade()
    print(f"   Área: {extent[1] - extent[0]:.0f} x {extent[3] - extent[2]:.0f} m, "
          f"grade {cols} x {rows} pixels de {RESOLUCAO} m")

    print("2. Carregando o terreno (MDT)...")
    terreno, fonte = carregar_terreno(transform, rows, cols)

    if MOSTRAR_EDIFICIOS:
        print("3. Baixando edifícios do OpenStreetMap...")
        superficie = terreno + carregar_edificios(transform, rows, cols)
        titulo = f"Terreno + edifícios (MDS)\nTerreno: {fonte} | Edifícios: OpenStreetMap"
    else:
        print("3. Edifícios desativados (MOSTRAR_EDIFICIOS = False).")
        superficie = terreno
        titulo = f"Terreno (MDT)\nFonte: {fonte}"

    print(f"   Altitude mínima: {np.nanmin(superficie):.1f} m")
    print(f"   Altitude máxima: {np.nanmax(superficie):.1f} m")

    print("4. Gerando o mapa...")
    fig, ax = plt.subplots(figsize=(10, 8))
    img = ax.imshow(superficie, cmap="terrain", extent=extent, origin="upper")
    fig.colorbar(img, ax=ax, label="Altitude (m)")
    ax.set_title(titulo)
    ax.set_xlabel("Easting (m) - SIRGAS 2000 / UTM 23S")
    ax.set_ylabel("Northing (m)")
    ax.ticklabel_format(style="plain", useOffset=False)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
