# UnityTranslator — Arquitectura

## 1. Propósito

UnityTranslator es una herramienta offline para extraer, editar, validar y reinyectar textos de juegos Unity sobre copias de trabajo. La instalación original se considera una fuente de solo lectura.

El flujo canónico es:

```text
GAME
 ↓
ANALYZE
 ↓
DETECT ADAPTERS
 ↓
EXTRACT
 ↓
TRANSLATION IR
 ↓
CSV / EDITOR
 ↓
IMPORT
 ↓
VALIDATE
 ↓
BACKUP + STAGING
 ↓
INJECT
 ↓
VERIFY
 ↓
BUILD TRANSLATED
```

La traducción automática no es una dependencia del sistema.

## 2. Stack real

- Python 3.11+.
- UnityPy para archivos Unity serializados.
- Cryptography para formatos cifrados conocidos.
- Tkinter/ttk para la GUI.
- `argparse` para la CLI.
- JSON versionado como persistencia inicial del Translation IR.
- Pytest.
- PyInstaller para el ejecutable Windows x64.

Runtime: offline. No se requiere IA, API, Supabase, cuenta ni conexión a Internet.

## 3. Capas actuales

```text
packaging/unity_translator_gui.py
        ↓
src/unity_translator/ui.py
        ↓
src/unity_translator/pipeline.py
        ↓
adapter registry / extractors
        ↓
UnityPy, cryptography, CSV, storage, validation
```

`ui.py` y `cli.py` orquestan operaciones. `pipeline.py` conserva la seguridad transaccional del proyecto. Los adaptadores no deben escribir sobre el juego fuente.

## 4. Componentes

### `analyzer.py`

Detecta:

- carpeta `*_Data`;
- Mono o IL2CPP;
- versión de Unity cuando `globalgamemanagers` lo permite;
- `StreamingAssets`;
- `Resources`;
- Addressables;
- assets y bundles visibles;
- señales por nombres de archivos.

La implementación actual produce inventario, firmas, candidatos ordenados por confianza, evidencia, limitaciones y niveles `automatic`, `assisted` e `investigation`. La búsqueda de `*_Data` está limitada a la carpeta seleccionada y un nivel descendiente; no realiza barridos ilimitados.

### `diagnostic_package.py`

Consume el resultado M2 y genera un paquete local `AI_CONTEXT/` más `AI_CONTEXT.zip` para investigación humana o por cualquier agente. Centraliza sanitización de rutas, exclusión de secretos/assets/ejecutables, límites del árbol y logs. El ZIP solo contiene metadata y guías generadas; no copia el juego. CLI: `unity-translator diagnose GAME [--output DIR]`.

### Registro de adaptadores

El registro será el único punto donde se enumeran adaptadores disponibles. El core debe consultar el registro, no conocer detalles de cada familia de formatos.

Cada adaptador declara:

```text
id
version
supported_formats
signatures
capabilities
limitations
confidence
```

### `pipeline.py`

Responsabilidades que permanecen en el core:

- crear y cargar proyectos;
- administrar manifest y Translation IR;
- importación/exportación CSV;
- validación común;
- snapshot y hashes;
- staging/build/restore;
- delegar extract/inject al adaptador seleccionado.

No debe contener reglas de cifrado, rutas específicas de un juego ni heurísticas de contenido de un framework.

### `validation.py`

Validadores comunes de placeholders, Rich Text/TMP, escapes y estados. Los adaptadores pueden aportar validadores adicionales para sintaxis propia, sin desactivar los validadores comunes.

### `storage.py`

Escrituras atómicas, JSON y hashes.

### `diagnostic_package.py`

Consume el resultado público sanitizado de M2 y genera un paquete local de investigación. No contiene lógica de extracción ni intenta abrir o modificar bundles. El árbol y el ZIP se construyen desde metadata; los archivos originales nunca se copian.

## 5. Translation IR

El IR actual es JSON y conserva la localización necesaria para reinyectar:

```json
{
  "schema_version": 1,
  "extractor": {"name": "...", "version": 1},
  "entries": [
    {
      "id": "stable-locator",
      "source_file": "Game_Data/StreamingAssets/dialogue.csv",
      "asset_type": "StreamingAssetsCSV",
      "object_identifier": "2:1",
      "field": "cell[2][1]",
      "original_text": "Start Game",
      "translated_text": "",
      "original_hash": "sha256:...",
      "status": "untranslated",
      "metadata": {}
    }
  ]
}
```

IDs, localizadores, texto original y hash son inmutables durante la importación. El campo `metadata` pertenece al adaptador y no debe perderse en un round-trip CSV/IR.

El manifiesto ya conserva un descriptor `adapter` compatible con proyectos existentes. El IR mantiene el extractor para no invalidar proyectos creados antes del registro; una migración explícita del campo `adapter` en IR queda para una versión posterior.

## 6. Proyectos y seguridad

```text
Project/
├── manifest.json
├── translation.json
├── originals/
├── translations/
├── builds/
├── backups/
└── logs/
```

Reglas:

1. El juego fuente nunca se modifica.
2. La extracción copia y hashea los archivos relevantes.
3. La inyección valida antes de crear el build.
4. Se crea backup antes de modificar el staging.
5. El build final se genera fuera de la instalación original.
6. Se releen y verifican las celdas modificadas.
7. Un fallo limpia el staging incompleto.

## 7. Niveles de compatibilidad

| Nivel | Significado |
|---|---|
| `automatic` | Adaptador detectado con evidencia suficiente; flujo offline sin selección manual |
| `assisted` | Hay candidatos; el usuario debe elegir un archivo, bundle, idioma o regla |
| `investigation` | Se genera diagnóstico; no se intenta una extracción destructiva |
| `experimental` | El adaptador funciona estructuralmente, pero falta cobertura/playtesting |
| `supported` | Adaptador verificado E2E y con playtesting documentado |

## 8. Estado actual

Adaptadores funcionales:

- `streamingassets-csv` — experimental.
- `unity-textasset-json` — experimental.
- `holyknight-encrypted-tsv` — experimental y probado con Holy Knight Ricca.

El analizador genérico M2 también registra el candidato diagnóstico `unity-addressables-textasset` cuando encuentra `StreamingAssets/aa` y bundles. Ese candidato solo tiene capacidades de análisis/detección y no puede crear un proyecto extraíble; esto es intencional y evita aplicar un perfil incompatible.

Detección parcial:

- `StreamingAssets/aa` y bundles Addressables — detectados, sin extractor automático todavía.

Pendientes principales:

- AssetBundles/Addressables.
- Unity Localization/String Tables.
- MonoBehaviour custom.
- Naninovel, Pixel Crushers, 2D Toolkit y otros frameworks.
- Paquete de diagnóstico sanitizado.
- Playtesting automatizado o checklist reproducible por adaptador.

El paquete diagnóstico se crea con `unity-translator diagnose <game>`, incluso para análisis `automatic` o `assisted`, para facilitar debugging. Sus límites y exclusiones están documentados en `adapter_api.md` y `expected_tests.md` dentro del paquete.

## 9. Decisiones de no alcance inmediato

No se priorizan ahora IA obligatoria, nube, Supabase, telemetría automática, autenticación, marketplace, SQLite ni diseño visual avanzado. Se preserva el camino para incorporarlos sin hacerlos necesarios para el flujo offline.
