# Prueba real — ERICA Knight of the Sun 0.1.9.2

Fecha: 2026-08-22.

## Detección

- Juego Unity detectado.
- Unity `2022.3.26f1`.
- Runtime Mono (`Managed/Assembly-CSharp.dll`).
- Sin `StreamingAssets`.
- Texto localizado en el `TextAsset` `TextData`, pathID `554`, dentro de `sharedassets0.assets`.
- Formato interno: JSON con `texts[]`, ID `dataID` e idiomas `KOR`, `ENG`, `JPN`, `CHN`.
- El juego ya tenía español escrito en `ENG`; los archivos `.bak` conservan variantes anteriores.

## Extracción con la aplicación

Perfil: extractor `unity-textasset-json`, campo `ENG`.

Resultado real:

- 950 objetos de texto en el JSON.
- 942 cadenas no vacías extraídas.
- 0 IDs duplicados.
- 0 originales vacíos exportados.

## Prueba de reinyección

Cambio deliberado y fácilmente identificable:

```text
Text_Quest3000
El apoyo de Bella
→
[PRUEBA MVP] Apoyo de Bella
```

Validación previa:

- 942 entradas comprobadas.
- 0 errores.
- 0 warnings.
- 1 traducción aplicada y 941 pendientes preservadas.

La primera ejecución reveló dos particularidades de Windows/OneDrive y se corrigieron:

1. `Path.replace()` no pudo promover el directorio de staging; se reemplazó por `shutil.move()`.
2. UnityPy mantenía abierto `sharedassets0.assets`; ahora se cierran explícitamente sus streams antes de reemplazar el archivo generado.

Resultado verificado:

- Build completo generado en `Project/builds/<timestamp>/game`.
- Ejecutable presente.
- Objetos Unity antes/después: `14322 → 14322`.
- Filas JSON antes/después: `950 → 950`.
- Diferencias semánticas: exactamente 1, la cadena prevista.
- El archivo fuente original quedó sin modificar.
- El build fue abierto y el proceso de Unity permaneció ejecutándose.

## Estado

La extracción, exportación, importación, validación, backup, reinyección y verificación estructural están demostradas sobre un juego real. Falta confirmación humana dentro de la pantalla concreta donde aparece `Text_Quest3000` y una prueba de recorrido del juego para promover este adapter de `experimental` a `supported`.
