# De la skill de traducción Unity al core determinista

## Evidencia inspeccionada

- Fuente canónica: `Hermes - Metodologia Traduccion Fan-made Unity/Skills/game-localization/unity-game-fan-translation/`.
- Referencias: corrección de `String[]` en type trees y verificación de glifos TMP.
- Experimentos reales: `extraccion 3 juegos`, especialmente Rose (UnityPy + Mono/type trees) y UnHolYJaiL (CSV en `StreamingAssets`).
- Scripts reales: extracción de dumps, reinyección UnityPy, reinyección por celda CSV y verificadores post-parche.
- El directorio de esta aplicación estaba vacío y no era un repositorio Git; no había sistema anterior que preservar dentro de él.

## Mapeo

| Paso actual | Qué hace | Herramienta/evidencia | Requiere IA | Automatizable | Implementación propuesta |
|---|---|---|---:|---:|---|
| Detectar Unity | Encuentra `_Data`, runtime Mono/IL2CPP y recursos | Estructura de archivos | No | Sí | `Analyzer` read-only con reporte y nivel de compatibilidad |
| Detectar versión | Lee versión del player/assets | `globalgamemanagers`, UnityPy cuando aplica | No | Sí, con límites | Heurísticas explícitas; `unknown` si no hay evidencia |
| Localizar dónde vive el texto | Decide entre assets, Localization, CSV, custom, código | Skill + inspección de DLL/dumps | Sí, en casos nuevos | Parcial | Detectores deterministas y extractores por adapter; nunca adivinar |
| Extraer CSV de StreamingAssets | Lee celdas y conserva coordenadas | Caso UnHolYJaiL probado | No | Sí | Primer adapter: CSV delimitado, ID estable `archivo:fila:columna` |
| Extraer `m_Text`/`m_text` | Lee objetos serializados | Rose: UnityPy | No si el type tree es conocido | Sí | Adapter posterior `UnityAssetsExtractor` |
| Extraer MonoBehaviour custom | Reconstruye type tree con DLL Mono | UnityPy + `TypeTreeGenerator` | Parcial | Sí para tipos conocidos | Adapter con preflight y fix defensivo de `String[]` |
| Preparar IL2CPP custom | Genera metadata usable | Il2CppDumper | Sí para interpretar sistemas nuevos | Parcial | Analyzer lo detecta; no soportado en primer milestone |
| Construir identificadores | Mantiene archivo, pathID/celda y campo | Scripts Rose/UnHolYJaiL | No | Sí | `TranslationEntry` + locator inmutable en metadata |
| Exportar para traductor | Genera CSV editable | CSV UTF-8 con BOM | No | Sí | Solo `id,original,translation,intentionally_empty` |
| Importar traducciones | Actualiza traducciones | Antes se confiaba en CSV del proyecto | No | Sí | Validación estricta de esquema, IDs, originales, duplicados y cobertura |
| Validar placeholders/tags | Evita romper formato | Skill y catálogo de bugs | No | Sí | Validadores puros con errores bloqueantes y warnings |
| Seleccionar idioma/tabla activa | Determina qué recurso lee el juego | Código o playtesting | Frecuentemente sí | Parcial | Perfil explícito; nunca elegir tabla destino por inferencia silenciosa |
| Reinyectar CSV plano | Sustituye celdas conservando las demás | UnHolYJaiL, flujo probado | No | Sí | Copia completa a `builds/`, edición puntual y escritura atómica |
| Reinyectar assets | `save_typetree`, staging y move | Rose, bug de save in-place confirmado | No con adapter conocido | Sí | Adapter posterior; prohibido guardar sobre el origen |
| Addressables CRC | Evita rechazo del bundle | Skill / logs `CRC Mismatch` | Parcial | Sí tras detectar catálogo | Experimental y fuera del primer milestone |
| Backup/rollback | Conserva originales | Reglas skill | No | Sí | Snapshot con hashes antes de inyectar; build separado; restore explícito |
| Verificación estructural | Relee campos, cuenta objetos, compara no tocados | Scripts verificadores | No | Sí | Verificador del adapter + manifiesto de hashes |
| Verificación jugando | Confirma carga, layout, ruta lingüística y estabilidad | Ejecución humana del juego | Sí/humana | No totalmente | Checklist manual obligatorio; la app no declarará compatibilidad completa sin esta prueba |
| Traducción automática | Traduce contenido | MT/LLM | Sí | No requerida | Fuera del MVP; únicamente `ManualProvider` |

## Qué ya demostró funcionar

1. **CSV plano en `StreamingAssets`**: extracción/reinyección por celda preservando filas y columnas no traducidas.
2. **Assets Mono conocidos**: UnityPy + metadata local, modificación agrupada por archivo/objeto, guardado a staging y relectura.
3. **Validación posterior**: comparar cada destino con el CSV, conteos estructurales y archivos no tocados.

## Qué no puede generalizarse todavía

- Qué celdas CSV son texto humano y cuáles son comandos.
- Qué tabla de idioma carga cada juego.
- Los campos custom de cada `MonoBehaviour`.
- IL2CPP custom, Addressables y todos los formatos de Localization.

Por eso el MVP usa niveles `supported`, `experimental`, `detected_unsupported` y `unknown`. El primer soporte es **experimental: CSV en StreamingAssets con perfil explícito de columnas**. El fixture de prueba usa un perfil conocido; no se escanean y modifican todas las celdas arbitrariamente.

## Decisión de alcance inicial

El tracer bullet implementa un adapter determinista `streamingassets-csv` con un archivo de perfil que define globs y columnas traducibles. Esto conserva la parte probada de UnHolYJaiL sin codificar reglas específicas de ese juego ni inventar una detección universal. La siguiente expansión será `UnityAssetsExtractor` para `m_Text`/`m_text`, respaldada por fixtures o un juego redistribuible de prueba.
