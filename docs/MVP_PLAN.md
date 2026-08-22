# Plan del MVP

## Principios

- Tracer bullets verticales y TDD: test fallando → implementación mínima → suite completa.
- Cada milestone termina con ejecución automatizada, prueba manual reproducible, evidencia documentada y commit pequeño.
- No se modifica ningún juego fuente; toda salida vive en `builds/`.

## M0 — Descubrimiento y contrato (este documento)

**Salida:** `SKILL_TO_CORE.md`, `ARCHITECTURE_MVP.md`, `MVP_PLAN.md`.

**Criterio:** decisiones distinguen evidencia, límites y pasos que aún requieren razonamiento humano.

## M1 — Tracer bullet `StreamingAssets CSV`

Alcance mínimo:

1. Analizar carpeta Unity (`*_Data`, runtime, Managed, StreamingAssets, assets, Addressables).
2. Crear proyecto con perfil explícito de CSV/columnas.
3. Extraer celdas a Translation IR JSON con hashes.
4. Exportar CSV UTF-8 BOM.
5. Importar CSV estrictamente.
6. Validar placeholders, tags, secuencias y estados.
7. Crear backup y build separado.
8. Reinyectar solo celdas traducidas.
9. Releer y verificar.
10. Exponer el flujo en CLI.

Prueba manual reproducible: fixture de juego Unity sintético con `Sample_Data/StreamingAssets/dialogue.csv`; cambiar una cadena y demostrar que únicamente cambia esa celda en el build. Luego ejecutar análisis/extracción read-only contra un juego real accesible, si su perfil puede definirse sin tocar su fuente.

**No incluye:** UnityPy/assets ni GUI.

## M2 — Robustez de frontera

Tests y comportamiento para:

- round-trip IR;
- CSV BOM/encoding;
- duplicados, desconocidos, faltantes y original modificado;
- vacío intencional;
- hashes de fuente cambiados;
- backup/restore;
- rollback de staging;
- archivos/celdas no tocados byte o semánticamente equivalentes.

## M3 — Unity assets built-in

Adapter UnityPy para `TextAsset`, `m_Text` y `m_text` con:

- detección/versionado de Unity;
- agrupación por archivo/objeto;
- guardado a staging, nunca in-place;
- relectura y conteo de objetos;
- fixtures legales/reproducibles y prueba contra un juego real compatible.

Solo después, evaluar MonoBehaviour custom + `TypeTreeGenerator` y fix `String[]`.

## M4 — UI mínima

Tkinter u otra UI fina sobre la API del core:

- seleccionar juego/proyecto;
- analizar, extraer, exportar/importar, validar, inyectar;
- tabla simple con búsqueda, edición, pendientes y errores;
- logs visibles.

La elección final de UI se valida cuando el CLI pruebe el ciclo E2E; no se construye dashboard ni diseño final.

## M5 — Prueba real y promoción de compatibilidad

Checklist de 12 puntos del objetivo, incluyendo abrir el juego, confirmar texto, flujo afectado y estabilidad. Hasta completar playtesting real, el adapter permanece `experimental`.

## Secuencia de commits prevista

1. `docs: map translation workflow to deterministic core`
2. `feat: add Unity analyzer and translation IR`
3. `feat: add strict CSV round trip`
4. `feat: add translation validation`
5. `feat: add safe StreamingAssets CSV injection`
6. `test: prove deterministic translation end to end`
7. `feat: add minimal desktop UI` (milestone posterior)

## Riesgos abiertos

- Un CSV arbitrario no revela por sí solo qué columnas son texto: se exige perfil.
- Reescribir CSV puede normalizar quoting/saltos; el verificador debe comparar celdas no objetivo y documentar cambios de bytes.
- La selección real de idioma puede depender de código/runtime: requiere perfil y playtesting.
- Fuentes/glifos y layout no se resuelven solo con validación textual.
- No hay aún juego fixture redistribuible con assets Unity serializados.
