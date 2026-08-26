# Unity Translator MVP

Motor offline y determinista para extraer, editar y reinyectar traducciones de juegos Unity. El soporte actual es **experimental** y cubre CSV bajo `StreamingAssets`, `TextAsset` JSON dentro de archivos Unity y tablas TSV cifradas de Holy Knight Ricca. El core usa un registro extensible de adaptadores; los formatos todavía desconocidos requieren investigación.

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

La ventana recorre el mismo pipeline del CLI y abre un editor manual con búsqueda, filtros por estado, edición de traducciones y marcado intencionalmente vacío. Al primer inicio muestra un tutorial textual opcional de cuatro pasos, que también queda accesible desde **Ver tutorial** o con `F1`. La UI llama al core; no contiene lógica de extracción o reinyección.

La interfaz usa una adaptación sobria del diseño visual de `Unity Translator Interface Design`: paneles oscuros, acento celeste, estados semánticos, agrupación por fases y registro técnico legible. Se conservaron únicamente patrones útiles para el flujo real; no se incluyen datos ficticios, imágenes de juego ni controles decorativos. La ventana tiene desplazamiento vertical mediante scrollbar y rueda del mouse para acceder al resultado y al registro en pantallas pequeñas.

## Ejecutable portable de Windows

El release portable se entrega como `UnityTranslator-0.1.0-windows-x64.zip`. Dentro encontrarás `UnityTranslator.exe`, tres perfiles JSON de ejemplo y `LEEME.txt`. No requiere Python instalado ni conexión a Internet durante el uso.

```text
UnityTranslator-0.1.0-windows-x64/
├── UnityTranslator.exe
├── profiles/
│   ├── streamingassets-dialogue.json
│   ├── unity-textasset-json.json
│   └── ERICA-TextData.json
└── LEEME.txt
```

Para regenerarlo desde Windows:

```bash
python -m PyInstaller --noconfirm --clean UnityTranslator.spec
```

El `.spec` incluye Tkinter/Tcl/Tk, UnityPy, dependencias detectadas, assets de la aplicación, icono y metadatos Windows. El ejecutable es Windows x64 y no está firmado digitalmente; SmartScreen puede mostrar una advertencia en el primer inicio.

## Flujo CLI

```bash
unity-translator analyze "C:/Games/MyGame"
unity-translator diagnose "C:/Games/MyUnknownGame" --output "C:/Diagnostics/MyUnknownGame"
```

`diagnose` genera únicamente metadata sanitizada, estructura acotada, señales, assemblies por nombre, candidatos, logs y guías en `AI_CONTEXT/AI_CONTEXT.zip`; no copia ejecutables, DLLs, assets, saves, traducciones completas ni secretos.

```bash
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

- Core, registro de adaptadores, IR JSON, CSV estricto, validación, backup, build separado, restore y CLI: implementados.
- TextAsset JSON con UnityPy: implementado y probado estructuralmente sobre ERICA Knight of the Sun 0.1.9.2.
- TSV cifrado de Holy Knight Ricca: implementado, autodetectado y probado con 688 archivos/14.394 cadenas.
- Otros assets serializados y MonoBehaviour custom: pendientes.
- Addressables/AssetBundles: detectados, pero todavía pendientes de extracción/reinyección.
- UI mínima y editor manual: implementados con Tkinter.
- Compatibilidad real: `experimental` hasta completar playtesting del juego resultante.

Ver `docs/` para arquitectura, mapeo de la skill y plan.
