# Unity Translator MVP

Motor offline y determinista para extraer, editar y reinyectar traducciones de juegos Unity. El soporte actual es **experimental** y cubre CSV bajo `StreamingAssets` y `TextAsset` JSON dentro de archivos Unity, siempre con un perfil explícito.

## Requisitos

- Python 3.11+
- Sin IA, APIs ni conexión a Internet en runtime

## Instalación de desarrollo

```bash
python -m pip install -e .
python -m pytest -q
```

## Interfaz mínima

```bash
unity-translator-gui
```

La ventana recorre el mismo pipeline del CLI y abre un editor manual con búsqueda, filtros por estado, edición de traducciones y marcado intencionalmente vacío. Al primer inicio muestra un tutorial opcional de cuatro pasos, que también queda accesible desde **Ver tutorial**. La UI llama al core; no contiene lógica de extracción o reinyección.

## Flujo CLI

```bash
unity-translator analyze "C:/Games/MyGame"

unity-translator init "C:/Games/MyGame" "C:/Translations/MyProject" \
  --profile examples/profiles/streamingassets-dialogue.json

unity-translator extract "C:/Translations/MyProject"
unity-translator export "C:/Translations/MyProject" "C:/Translations/es-MX.csv"
# Editar únicamente translation e intentionally_empty
unity-translator import "C:/Translations/MyProject" "C:/Translations/es-MX.csv"
unity-translator validate "C:/Translations/MyProject"
unity-translator inject "C:/Translations/MyProject"
```

`inject` genera una copia completa en `Project/builds/<timestamp>/game`; nunca modifica el juego fuente. Antes crea un snapshot en `Project/backups/<timestamp>`.

Restauración explícita sobre una copia/destino:

```bash
unity-translator restore PROJECT BACKUP_NAME DESTINATION_GAME_COPY
```

## Perfil CSV

```json
{
  "extractor": "streamingassets-csv",
  "files": [
    {
      "glob": "dialogue.csv",
      "columns": [1],
      "header": true,
      "encoding": "utf-8-sig",
      "delimiter": ","
    }
  ]
}
```

Los globs son relativos a `<Juego>_Data/StreamingAssets`. No uses columnas inferidas: deben conocerse por documentación, inspección o prueba del juego.

## Perfil TextAsset JSON

```json
{
  "extractor": "unity-textasset-json",
  "asset_file": "sharedassets0.assets",
  "textasset": {"name": "TextData", "path_id": 554},
  "list_key": "texts",
  "id_field": "dataID",
  "text_field": "ENG"
}
```

La app modifica el `TextAsset` únicamente en el build generado, guarda UnityPy en staging, cierra los handles de Windows y relee el asset para verificar el JSON y el conteo de objetos.

## Estado

- Core, IR JSON, CSV estricto, validación, backup, build separado, restore y CLI: implementados.
- TextAsset JSON con UnityPy: implementado y probado estructuralmente sobre ERICA Knight of the Sun 0.1.9.2.
- Otros assets serializados y MonoBehaviour custom: pendientes.
- UI mínima y editor manual: implementados con Tkinter.
- Compatibilidad real: `experimental` hasta completar playtesting del juego resultante.

Ver `docs/` para arquitectura, mapeo de la skill y plan.
