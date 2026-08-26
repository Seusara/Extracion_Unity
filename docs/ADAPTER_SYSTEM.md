# Sistema de adaptadores

## Objetivo

Permitir agregar soporte para una familia de formatos sin modificar todas las capas del core. Un adaptador debe encapsular detección, extracción, validación específica, reinyección y verificación.

## Contrato propuesto

```python
class Adapter:
    id: str
    version: int
    supported_formats: tuple[str, ...]
    capabilities: frozenset[str]
    limitations: tuple[str, ...]

    def detect(self, analysis: dict) -> DetectionResult: ...
    def analyze(self, context: AnalysisContext) -> dict: ...
    def extract(self, context: ProjectContext) -> ExtractionResult: ...
    def validate(self, context: ProjectContext) -> list[ValidationIssue]: ...
    def inject(self, context: InjectionContext) -> InjectionResult: ...
    def verify(self, context: VerificationContext) -> VerificationResult: ...
```

La primera implementación puede usar `Protocol`/dataclasses y funciones existentes. No hace falta introducir una jerarquía compleja antes de tener dos o tres adaptadores reales.

## Descriptor

Cada adaptador registrado debe describirse con datos serializables:

```json
{
  "id": "streamingassets-csv",
  "version": 1,
  "supported_formats": ["csv"],
  "signatures": ["StreamingAssets/*.csv"],
  "capabilities": ["extract", "export", "import", "validate", "inject", "verify"],
  "limitations": ["columns require a profile"],
  "support": "experimental"
}
```

## Registro

La primera versión del registro ya está implementada en `src/unity_translator/adapters.py`. La integración actual cubre resolución por ID, descriptores, validación de perfiles, extracción e inyección, manteniendo las implementaciones probadas en sus módulos actuales.

El registro debe:

- conocer todos los adaptadores incorporados;
- devolver un adaptador por ID/version;
- devolver descriptores para el analizador/UI/CLI;
- no leer archivos de juegos al importar el módulo;
- ser determinista y fácil de probar;
- permitir agregar una implementación sin modificar el registro de cada operación del pipeline.

La detección puede devolver varios candidatos:

```json
{
  "adapter": "unity-addressables-textasset",
  "confidence": 0.82,
  "evidence": ["StreamingAssets/aa", "42 bundles inspected", "TextAsset JSON found"],
  "limitations": ["catalog destination not verified"]
}
```

## Adaptadores existentes

### `streamingassets-csv`

- Fuente: archivos CSV relativos a `StreamingAssets`.
- Localizador: archivo/fila/columna.
- Requiere perfil para columnas y encabezado.
- Reinyección por celda.

### `unity-textasset-json`

- Fuente: `TextAsset` dentro de `.assets` o archivo Unity compatible con UnityPy.
- Localizador: archivo/path ID/lista/campo/índice.
- Requiere perfil explícito.
- No debe asumir `sharedassets0.assets`.

### `holyknight-encrypted-tsv`

- Fuente: TSV cifrado en `StreamingAssets/Lang/en/*.dat`.
- Descarta `.dat` bajo `image/`.
- Localizador: archivo/key/fila/columna.
- Reinyección cifrada sobre copia.
- Actualmente es un adaptador de familia observada; debe separarse de cualquier nombre de juego.

## Próximo adaptador: Addressables

Debe ser una familia genérica, no una condición `if game == CIRCLEMATE`.

Proceso esperado:

1. Detectar `StreamingAssets/aa` y plataformas disponibles.
2. Leer catálogos cuando sean accesibles.
3. Enumerar bundles candidatos.
4. Abrirlos en modo lectura con UnityPy.
5. Inspeccionar `TextAsset`, JSON, CSV, String Tables y objetos de localización.
6. Calcular confianza a partir de varias señales.
7. En nivel `assisted`, mostrar candidatos al usuario.
8. Guardar en IR el bundle, objeto, path ID, tipo y campo.
9. Reinyectar sobre una copia.
10. Verificar bundle, catálogo, CRC y referencias antes de declarar éxito.

Si el bundle no puede guardarse sin romper el catálogo, el adaptador debe quedar en `investigation` o `assisted`, no inyectar silenciosamente.

## Validación específica

Un adaptador puede registrar reglas propias, por ejemplo:

- sintaxis de comandos;
- identificadores no traducibles;
- marcadores de framework;
- claves de String Table;
- campos que deben conservarse byte a byte.

Las reglas comunes de placeholders/tags/escapes continúan aplicándose.

## Tests mínimos por adaptador

Cada adaptador nuevo debe aportar:

1. Detección positiva.
2. Detección negativa.
3. Confianza/evidencia estable.
4. Extracción a IR.
5. Export/import round-trip.
6. Reinyección de una sola cadena.
7. Verificación post-inyección.
8. Archivo original sin cambios.
9. Error claro para formato incompleto.
10. Fixture legal y pequeño, sin redistribuir assets con copyright.
