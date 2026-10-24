# Dados de calibração World3D

Arquivos de referência usados para gerar
[`is_viewer/web/static/world3d-scene.json`](../../is_viewer/web/static/world3d-scene.json).
Os NPZ originais foram copiados sem alterar os valores.

| Arquivo | Câmera | Formato de `rt` | Tamanho |
| --- | ---: | --- | ---: |
| `calibrations/calib_rt1.npz` | 1 | 4 × 4 | 2.896 B |
| `calibrations/calib_rt2.npz` | 2 | 4 × 4 | 2.899 B |
| `calibrations/calib_rt3.npz` | 3 | 4 × 4 | 2.898 B |
| `calibrations/calib_rt4.npz` | 4 | 4 × 4 | 2.898 B |
| `calibrations/calib_rt6.npz` | 6 | 3 × 4 | 2.254 B |
| `calibrations/calib_rt7.npz` | 7 | 3 × 4 | 2.254 B |
| `calibrations/calib_rt8.npz` | 8 | 3 × 4 | 2.254 B |
| `map_B3A1.npz` | — | 4 contornos XYZ; coordenadas em metros, Z = 0 | 15.974 B |

As sete calibrações totalizam 18.353 B; o mapa ocupa 15.974 B. Os hashes abaixo
identificam os bytes dos arquivos usados na cena JSON.

```text
051277a206593f957147a4c4ebd33d62cde10ce841ea15ecc1cd09f410b159cd  calibrations/calib_rt1.npz
b09f118bb3d1aa2597ccf76a33b96822407ef0f2c27e90d21b6e5fd12afd2a69  calibrations/calib_rt2.npz
2fa5576485c03eecf4b230b9a4f77935aee76afe4ebc742b32cf64aba386035d  calibrations/calib_rt3.npz
7fb8509c0b2e397bd54b59aeca040b4414fca0617a0a0c76badff7a6f57d4cc0  calibrations/calib_rt4.npz
4bd05bf7625d1ba190ac6e7c92b6bdfc5ee3a8ca28a3cd27d8859e87ec279eea  calibrations/calib_rt6.npz
b251d70fe125d45c7ed889aa14cdf318bef96ca00e873ba3eb769bd101fe1e1c  calibrations/calib_rt7.npz
d60fd36515ed940a416ec48b497e97017e9a17bf8a600ae0dcb754e2e65b8ca5  calibrations/calib_rt8.npz
cae880921baebbf8f13495aaddaf3603e0f2e2b8e4afe0f9b110d1e25d14abb0  map_B3A1.npz
```

`rt` transforma pontos do mundo para o sistema da câmera. A posição usada no
viewer é `-Rᵀt`; todas as câmeras ficam no referencial calibrado Z-up. O mapa é
usado diretamente nesse mesmo referencial, sem deslocamento ou redimensionamento.
A câmera 5 não tem calibração neste conjunto.

O modelo sintético usado com esses dados foi incluído em
[`is_viewer/web/static/models/labsea.glb`](../../is_viewer/web/static/models/labsea.glb).
Sua origem, hash e transformação de eixos estão no [guia do GLB](../../docs/labsea-glb.md).

## Regenerar os dados para o viewer

A partir da raiz do repositório, com NumPy instalado:

```bash
python scripts/import_world3d.py --trust-map-pickle
```

Os NPZ do mapa usam uma lista NumPy serializada com pickle. Use o opt-in apenas
com este arquivo versionado e confiável. O servidor não abre NPZ; recebe somente
o JSON numérico gerado. Para atualizar calibrações, atualize primeiro os NPZ e
seus hashes nesta pasta e então regenere o JSON.
