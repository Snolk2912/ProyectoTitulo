# Réplica offline de 2-SMA con LB²

El proyecto simula una estrategia de dos medias móviles sobre velas BTCUSDT de
15 minutos y optimiza sus seis parámetros con Learning-Based Linear Balancer
(LB², llamado LV2 en las notas originales).

La definición del experimento está en [docs/replication.md](docs/replication.md).
Documenta las contradicciones de los dos artículos y las decisiones adoptadas
sobre fechas, ventanas, FSM, ejecución, contabilidad y regresiones. Los resultados
de los artículos son referencias; la implementación no presupone reproducir sus
porcentajes de rentabilidad.

## Datos y dependencias

Se trabaja exclusivamente con un **CSV local original** con estas columnas:

```text
open_time,open,high,low,close,volume
```

`open_time` acepta ISO con zona horaria o milisegundos UTC. Las velas deben estar
ordenadas, ser únicas y consecutivas cada 15 minutos, con OHLCV válido. No se
acepta un CSV de ventanas que repita precios, ni se eliminan filas para ocultar
huecos o errores.

Requiere Python 3.10+ y NumPy. Los comandos funcionan desde la raíz del proyecto
sin instalar el paquete si NumPy ya está disponible. `pyproject.toml` declara
las dependencias; Matplotlib es opcional para gráficos y pytest para las pruebas.
Pandas ya no es necesario.

La ruta de entrada predeterminada es:

```text
data_processed/BTCUSDT_15m_20190910_20220131_processed.csv
```

Si el archivo falta, el programa informa el error. Los comandos de auditoría,
ventanas, simulación, comparación y LB² no acceden a la red. El script (1)
permanece como utilidad manual separada, deshabilitada salvo habilitación
explícita; no forma parte del flujo de trabajo de este entorno.

## Ejecutar el experimento completo

```bash
python -m trading.cli run \
  --data data_processed/BTCUSDT_15m_20190910_20220131_processed.csv \
  --output results/experiment \
  --seed 42 --population 20 --iterations 100 --learning-interval 20
```

Esta ejecución valida el CSV, construye las ventanas, optimiza exclusivamente en
train y compara el candidato seleccionado con SMA fija, Buy and Hold y Random
Walk en train/test. El Random Walk se calibra con retornos únicos de train.
Se informan por separado las medias geométrica y aritmética.

Defaults del experimento:

| Ajuste | Valor |
|---|---|
| Ventana / avance | 60 / 30 días |
| Historia previa común | 1344 velas |
| Test | Últimas 8 ventanas completas |
| Separación | Se purgan las ventanas train que invaden test |
| Capital / leverage | 1 USDT / 1 |
| Comisión por fill | 0.0004 sobre notional ejecutado |
| Deslizamiento | 0 puntos básicos |
| Objetivo | Maximizar la media de logaritmos de factores netos en train |
| LB² | 20 agentes, 100 iteraciones, aprendizaje cada 20, semilla 42 |

El primer inicio se ancla después de la historia previa disponible. No se fuerza
la cantidad de ventanas a 23/8: depende de las fechas del CSV y de la purga.
`--start` y `--end` permiten fijar un rango UTC; el límite final es exclusivo.

El presupuesto puede cambiarse con los argumentos del comando. El tiempo
depende de las ventanas, agentes, iteraciones y esquemas elegidos; las trazas
registran la cantidad efectiva de evaluaciones. Se realiza un holdout
cronológico por ejecución, sin inventar las 34 particiones no especificadas
completamente en el artículo.

## Ejecución por etapas

```bash
python -m trading.cli audit --data /ruta/ohlcv.csv
python -m trading.cli windows --data /ruta/ohlcv.csv
python -m trading.cli simulate --data /ruta/ohlcv.csv --window-id 0
python -m trading.cli optimize --data /ruta/ohlcv.csv --output results/lb2
python -m trading.cli baselines --data /ruta/ohlcv.csv \
  --parameters results/lb2/parameters.json --output results/comparison
```

`optimize` no evalúa test. `simulate` y `baselines` heredan capital, comisiones,
leverage y deslizamiento guardados en `parameters.json`; un argumento explícito
puede sustituirlos. Sin ese archivo usan la configuración publicada como
referencia fija. Para cambiar los límites de búsqueda, `--search-space` acepta
un JSON con los campos de `trading.lb2.SearchSpace`.

La ayuda de cada comando enumera sus argumentos:

```bash
python -m trading.cli run --help
```

## Salidas

El directorio de `run` contiene:

- `experiment.json`: configuración, versiones Python/NumPy y SHA-256 del CSV.
- `windows.csv`: fechas, índices y etiquetas train/test/purged, sin repetir OHLCV.
- `parameters.json`: candidato seleccionado y fitness de entrenamiento.
- `optimizer.json`: evolución, evaluaciones, regresiones y probabilidades de LB².
- `evaluation.json` y `comparison.csv`: factores por ventana y resúmenes.
- `trades.csv`: operaciones, precios ejecutados, cantidades, comisiones y PnL.
- `equity.csv`: curva por ventana y estrategia si se usa `--save-equity`.

Con `--plots` se guardan `roi_by_window.png` y `capital_by_test_window.png`.
El segundo muestra factores independientes por ventana, sin acumular periodos
solapados. Los gráficos requieren Matplotlib.

## Motor y LB²

La FSM sigue la figura 3: entradas por relación entre SMA y destinos de los stops
condicionados por ese régimen. Se decide con cierres y se ejecuta en la siguiente
apertura. Los trailing usan precios posteriores a la entrada; una posición
pendiente se liquida al último cierre. El PnL long/short es lineal USDT y las
comisiones se aplican a los dos notionals efectivos.

LB² usa movimientos SHO en un dominio normalizado, dos ruletas independientes
de intensificación/diversificación, esquemas de 1/2/3 movimientos y seis
regresiones periódicas. Conserva el mejor candidato evaluado y selecciona el
máximo fitness predicho. La especificación registra las decisiones necesarias
para completar el pseudocódigo ambiguo del artículo 09.

Funding y las reglas de margen/liquidación del exchange quedan fuera del
modelo. La insolvencia se trata mediante una regla explícita de equity cero en
aperturas/cierres. Estas hipótesis y los límites finitos de los stop-win figuran
en la especificación.

## Scripts originales

Las entradas numeradas permanecen disponibles y delegan en el motor común:

| Script | Comando equivalente |
|---|---|
| (1) | Utilidad manual separada; fuera del experimento offline |
| (2) | `audit` |
| (3) | `windows`, exporta un manifiesto |
| (6) | `plot --single --fast 50 --slow 200` |
| (7) | `plot --fast 17 --slow 50` |
| (9) | `plot --fsm --fast 17 --slow 50`, gráfico y JSON de la FSM con riesgo |
| (10) | `simulate`, configuración publicada |
| (11) | `baselines` |

Importarlos no ejecuta operaciones. Sus rutas de salida están dentro de este
repositorio. Los argumentos posteriores sustituyen sus valores predeterminados.
El benchmark es **Random Walk**; este repositorio no incluye Random Forest.

## Verificación

```bash
python -m pytest -q
```

Las pruebas verifican fills causales, gaps, stops, PnL short, comisiones,
liquidación final, insolvencia, aislamiento de test, ventanas, aprendizaje de
LB², determinismo y el flujo completo con un CSV sintético. Se bloquea el acceso
de red en las pruebas de importación y CLI. No se han medido resultados sobre
BTCUSDT real porque no hay un CSV local incluido en este repositorio.
