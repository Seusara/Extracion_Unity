# UnityTranslator — Resumen de continuidad

## Objetivo

Continuar el desarrollo de **UnityTranslator**, una aplicación Windows portable, offline y orientada a localizar juegos Unity sin modificar la instalación original.

El proyecto debe:

- Detectar automáticamente juegos Unity.
- Reconocer Mono e IL2CPP.
- Trabajar con distintas versiones y estructuras de Unity.
- Detectar perfiles/extractores compatibles antes de extraer.
- Extraer, editar, validar, reinyectar y generar una copia traducida.
- Mantener separados juego original, proyecto, backups y builds.
- Distribuirse como `.exe` portable mediante PyInstaller.
- No depender de APIs externas, IA ni conexión a Internet durante el uso.

## Repositorio y estado

- Repositorio: `https://github.com/Seusara/Extracion_Unity`
- Rama de trabajo: `feat/mvp-deterministic-core`
- Último commit relevante: `3928ab6 docs: add Unity continuation handoff` (la integración del registro queda en el commit siguiente de esta sesión)
- Proyecto local: `C:\Users\aron-\OneDrive\Desktop\app extraccion unity`
- Tests actuales antes de este milestone: 36 pasando; el registro de adaptadores agrega 3 tests.
- Verificación habitual:

```bash
python -m pytest -q
git diff --check
```

## Arquitectura actual

```text
packaging/unity_translator_gui.py
        ↓
src/unity_translator/ui.py
        ↓
src/unity_translator/pipeline.py
        ↓
extractors / holyknight / unity_json / validation / storage
```

### Regla importante

La UI debe ser delgada. No debe duplicar extracción, validación ni reinyección. Todas las operaciones deben pasar por `pipeline.py`.

## Archivos principales

- `src/unity_translator/analyzer.py`
  - Detecta `*_Data`.
  - Determina Mono/IL2CPP.
  - Detecta StreamingAssets, Resources, Addressables y assets conocidos.
  - Sugiere perfiles automáticos para formatos reconocidos.

- `src/unity_translator/pipeline.py`
  - Crea proyectos.
  - Extrae.
  - Importa/exporta CSV.
  - Valida.
  - Genera backups.
  - Inyecta sobre una copia.
  - Genera y verifica builds.

- `src/unity_translator/ui.py`
  - Interfaz Tkinter/ttk.
  - Flujo por etapas.
  - Perfil automático.
  - Editor manual.
  - Validación e informes.
  - Selección de destino para exportar CSV.

- `src/unity_translator/holyknight.py`
  - Extractor específico para Holy Knight Ricca.
  - Lee tablas TSV cifradas en `StreamingAssets/Lang/en/*.dat`.
  - Excluye `Lang/en/image/*.dat`, que son imágenes y no texto.
  - Reinyecta textos cifrados en builds separadas.

- `src/unity_translator/validation.py`
  - Valida placeholders.
  - Valida etiquetas/rich text.
  - Valida atributos de etiquetas.
  - Valida escapes `\\n`, `\\r`, `\\t`, `\\\\`.
  - Marca traducciones sin cambios y vacías intencionales como advertencias.

- `tests/`
  - Tests unitarios, E2E, UI, resolución de assets, Holy Knight y reportes de validación.

## Formatos soportados actualmente

### 1. CSV en StreamingAssets

Perfil existente:

```text
streamingassets-dialogue.json
```

Detecta actualmente `StreamingAssets/dialogue.csv` en la ubicación esperada.

### 2. TextAsset JSON en archivos Unity

Perfil existente:

```text
unity-textasset-json.json
```

Requiere declarar explícitamente:

- `asset_file`.
- `textasset.name`.
- `textasset.path_id`.
- `list_key`.
- `id_field`.
- `text_field`.

No se debe asumir que el juego tiene `sharedassets0.assets`.

### 3. Holy Knight Ricca

Perfil automático:

```json
{
  "extractor": "holyknight-encrypted-tsv",
  "source_root": "StreamingAssets/Lang/en"
}
```

Prueba real confirmada:

```text
Runtime: IL2CPP
Archivos procesados: 688
Cadenas extraídas: 14.394
```

La extracción y reinyección se ejecutan sobre una copia. El juego original no se modifica.

## Validación e informes

Cada validación escribe:

```text
<proyecto>\logs\validation-report.json
<proyecto>\logs\validation-report.csv
```

Los informes contienen:

- Severidad.
- Código.
- ID.
- Archivo origen.
- Estado.
- Texto original.
- Traducción.
- Mensaje y secuencia problemática cuando corresponde.

La UI contiene:

- `Validar traducciones`.
- `Corregir problemas seguros`.
- `Abrir informe detallado`.

La corrección automática actual solo restablece traducciones idénticas al original a estado `untranslated`. No debe alterar automáticamente placeholders, etiquetas o escapes sin una regla segura y verificable.

Durante la reinyección, si existen errores, el pipeline debe bloquear la operación. El error actualizado muestra:

- Cantidad de errores.
- Códigos agrupados.
- Hasta cinco IDs afectados.
- Ruta al informe CSV.

## Problema conocido: falsos positivos y advertencias

Textos como:

```text
mhh... ...Ya... Basta...
```

son texto plano válido y no deberían considerarse código dañado.

Las advertencias de `unchanged_translation` significan que la traducción es idéntica al original; no son necesariamente errores de formato.

No se debe eliminar la validación de placeholders, etiquetas o escapes para permitir la inyección. Primero hay que revisar el informe detallado y determinar si el formato del juego utiliza una sintaxis especial que el validador no reconoce.

## Registro de adaptadores

El core ahora dispone de `src/unity_translator/adapters.py`, con descriptores, capacidades, limitaciones, validación de perfiles y delegación común para los tres adaptadores existentes. `pipeline.py` consulta el registro para crear proyectos, extraer e inyectar.

El registro es el primer paso de la arquitectura extensible. Las implementaciones concretas todavía viven en sus módulos actuales y deben extraerse gradualmente del pipeline solo cuando exista una prueba que justifique el cambio.

## Siguiente formato prioritario: Addressables / AssetBundles

Caso reportado:

```text
CIRCLEMATE-ENG
```

Estructura observada:

```text
CIRCLEMATE_Data/
└── StreamingAssets/
    └── aa/
        └── StandaloneWindows64/
            └── *.bundle
```

El extractor actual falla si se usa un perfil que espera:

```text
sharedassets0.assets
```

Esto no significa que el juego esté roto. Significa que usa AssetBundles/Addressables y todavía no existe un extractor automático para ese patrón.

### Trabajo pendiente para Addressables

Implementar un detector y extractor que:

1. Detecte `StreamingAssets/aa`.
2. Enumere bundles sin asumir nombres.
3. Abra bundles con UnityPy.
4. Inspeccione `TextAsset`, JSON, CSV, String Tables y objetos de localización.
5. Identifique candidatos por contenido, no solo por nombre.
6. Genere un perfil automático con:
   - bundle origen;
   - nombre/path ID del objeto;
   - formato;
   - lista y campos de texto.
7. Permita revisión cuando haya varios candidatos.
8. Reinyecte en una copia y verifique que el bundle siga siendo legible.
9. Informe qué bundles fueron inspeccionados y por qué fueron descartados.

No se debe probar todos los bundles destructivamente ni reinyectar sobre la instalación original.

## Mejoras recomendadas del analizador universal

El analizador debería devolver un inventario estructurado, no solo un contador:

```json
{
  "data_dir": "...",
  "runtime": "il2cpp",
  "unity_version": "unknown",
  "asset_files": [],
  "bundle_files": [],
  "streaming_files": [],
  "addressables": true,
  "candidate_profiles": [],
  "unsupported_reasons": []
}
```

Debe distinguir claramente entre:

- Assets Unity serializados (`.assets`).
- AssetBundles (`.bundle`).
- Archivos de recursos (`.resource`).
- Archivos de texto externos.
- Datos cifrados.
- Catálogos Addressables.

Nunca convertir automáticamente un `.resource` en un supuesto `.assets`.

## Selección de carpeta

`find_data_dir()` actualmente espera exactamente una carpeta `*_Data` directamente dentro de la carpeta seleccionada.

Si falla con:

```text
Expected exactly one *_Data directory
```

puede significar:

- Se seleccionó una carpeta demasiado arriba.
- Hay varias instalaciones dentro de la carpeta.
- El ejecutable seleccionado no está junto a su carpeta `*_Data`.

Una mejora posible es ofrecer una búsqueda controlada de `*_Data` en un nivel descendiente, mostrando candidatos al usuario en vez de fallar ambiguamente.

## Distribución

Build local:

```text
dist/UnityTranslator.exe
```

Distribución portable:

```text
release/UnityTranslator-0.1.0-windows-x64/
release/UnityTranslator-0.1.0-windows-x64.zip
```

Build:

```bash
python -m PyInstaller --noconfirm --clean UnityTranslator.spec
```

El ejecutable usa modo `--windowed` y debe iniciar sin consola visible.

Después de cada corrección importante:

1. Ejecutar tests.
2. Ejecutar `git diff --check`.
3. Reconstruir con PyInstaller.
4. Copiar el `.exe` a `release/`.
5. Regenerar el ZIP.
6. Publicar los dos assets en la release `v0.1.0`.
7. Descargar el `.exe` publicado y comparar SHA-256 con el local.

Assets actuales:

```text
https://github.com/Seusara/Extracion_Unity/releases/download/v0.1.0/UnityTranslator.exe
https://github.com/Seusara/Extracion_Unity/releases/download/v0.1.0/UnityTranslator-0.1.0-windows-x64.zip
```

## Reglas de seguridad

- No modificar nunca el juego original.
- No leer ni publicar credenciales o secretos.
- No incluir capturas o branding de ERICA.
- No afirmar compatibilidad sin una extracción real.
- No ocultar errores para permitir una inyección dudosa.
- Toda inyección debe usar copia, staging, backup y verificación.
- Si el formato no es conocido, generar diagnóstico y pedir inspección, no elegir un perfil al azar.

## Primeras tareas recomendadas

1. Confirmar que el usuario está usando el último `.exe` descargado y no una copia antigua.
2. Revisar los 21 errores reales del `validation-report.csv` actual.
3. Determinar si son falsos positivos por sintaxis específica del juego.
4. Añadir tests para cada falso positivo confirmado.
5. Implementar descubrimiento Addressables/AssetBundles.
6. Probarlo con una copia accesible de `CIRCLEMATE-ENG`.
7. Separar en el informe:
   - errores bloqueantes reales;
   - advertencias informativas;
   - textos sin cambios;
   - pendientes.
8. Volver a construir y publicar el ejecutable solo después de una extracción y validación reales.
