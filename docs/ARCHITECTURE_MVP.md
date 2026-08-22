# Arquitectura del MVP

## Decisión tecnológica

**Python 3.11+** para core, CLI, tests y primera UI (Tkinter más adelante).

Motivo: UnityPy y las herramientas probadas del proceso existente viven en Python; una UI React/Electron agregaría dos runtimes y complejidad antes de probar el motor. El core no depende de Tkinter. Si luego se adopta React, consumirá la misma API/CLI sin mover lógica a la UI.

## Capas

```text
unity_translator/
├── core/
│   ├── analyzer.py
│   ├── ir.py
│   ├── project.py
│   ├── csv_io.py
│   ├── validation.py
│   ├── backup.py
│   └── pipeline.py
├── extractors/
│   ├── base.py
│   └── streamingassets_csv.py
├── injectors/
│   ├── base.py
│   └── streamingassets_csv.py
├── providers/
│   └── manual.py
├── cli.py
└── ui/                 # después del core E2E
```

Dirección de dependencias: UI/CLI → pipeline/core → puertos de extractor/injector. Los adapters pueden usar librerías externas; el dominio no conoce UnityPy ni Tkinter.

## API objetivo

```python
analyze(game_path)
create_project(game_path, project_path, profile)
extract(project_path)
export_csv(project_path, locale)
import_csv(project_path, csv_path)
validate(project_path)
inject(project_path)
```

Las operaciones retornan resultados estructurados; el CLI decide cómo imprimirlos.

## Translation IR

Persistencia inicial: JSON versionado y escrito atómicamente. SQLite se evaluará cuando el editor necesite consultas concurrentes o volúmenes que lo justifiquen.

```json
{
  "schema_version": 1,
  "entries": [{
    "id": "StreamingAssets/dialogue.csv:2:1",
    "source_file": "Sample_Data/StreamingAssets/dialogue.csv",
    "asset_type": "StreamingAssetsCSV",
    "object_identifier": "2:1",
    "field": "cell[2][1]",
    "original_text": "Start Game",
    "translated_text": "",
    "original_hash": "sha256:...",
    "status": "untranslated",
    "metadata": {"row": 2, "column": 1, "encoding": "utf-8-sig"}
  }]
}
```

`id`, localizador, original y hash son inmutables durante la importación. Una traducción vacía solo se inyecta si `intentionally_empty=true`.

## Proyecto en disco

```text
Project/
├── manifest.json
├── translation.json
├── originals/          # snapshot de archivos fuente necesarios
├── translations/
├── builds/             # salida; nunca el juego fuente
├── backups/            # snapshot + manifiestos de hash
└── logs/
```

El manifiesto registra versión de herramienta/esquema, extractor, perfil, ruta fuente, runtime, Unity detectada, timestamps y hashes.

## Contrato de adapters

### Extractor

- declara `name`, versión y nivel de soporte;
- `probe(analysis, profile)` explica por qué aplica;
- `extract(context) -> list[TranslationEntry]`;
- no escribe el juego;
- IDs únicos y localizadores suficientes para reinyección.

### Injector

- valida que el adapter y versión coincidan con la extracción;
- verifica hashes contra `originals/`;
- escribe solo en staging/build;
- modifica únicamente localizadores presentes y traducidos;
- relee y verifica cada cambio;
- produce manifiesto de archivos cambiados y hashes.

## CSV externo

UTF-8 con BOM para Excel:

```csv
id,original,translation,intentionally_empty
...
```

Importación transaccional: parsear y validar todo antes de escribir IR. Errores bloqueantes: BOM/UTF-8 inválido, cabecera inválida, ID duplicado/desconocido/faltante, original cambiado. Ningún cambio parcial.

## Validación

`ValidationIssue {severity, code, entry_id, message, details}`.

Bloqueantes iniciales:

- hash/original cambiado;
- placeholders faltantes o modificados (`{0}`, `{name}`, `%s`, `%d`);
- tags Rich Text/TMP rotos o con firma distinta;
- secuencias escapadas requeridas faltantes;
- traducción pendiente cuando el modo exige cobertura completa.

Warnings: traducción idéntica al original, longitud extrema y traducción vacía intencional.

## Seguridad y recuperación

1. La extracción copia los archivos relevantes a `originals/` y hashea fuente/copia.
2. La inyección valida IR, perfil y hashes.
3. Crea backup versionado de `originals/`.
4. Genera `builds/<timestamp>/game/` desde copia.
5. Escribe a archivo temporal y usa replace atómico dentro del build.
6. Relee celdas y compara todos los destinos.
7. En fallo elimina/declara incompleto el staging; la fuente nunca se modifica.

## Compatibilidad inicial

| Nivel | Significado |
|---|---|
| Supported | Adapter verificado E2E y juego ejecutado después del parche |
| Experimental | E2E estructural verificado; falta playtesting real o cobertura amplia |
| Detected but unsupported | Se reconoce el sistema, pero no existe adapter seguro |
| Unknown | Evidencia insuficiente |

Primer adapter: `streamingassets-csv`, **experimental** hasta ejecutar un juego real parchado mediante esta aplicación.

## No tocar todavía

UI elaborada, IA, nube, auth, plugins públicos, Addressables write, IL2CPP custom y promesas de compatibilidad universal.
