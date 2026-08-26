# Roadmap de UnityTranslator

## Estado base — completado

- [x] Core offline y determinista.
- [x] CLI y GUI sobre el mismo pipeline.
- [x] Translation IR JSON.
- [x] CSV estricto con round-trip.
- [x] Validación de placeholders, tags, escapes y hashes.
- [x] Backups, staging, builds separados y restore.
- [x] Perfil CSV en StreamingAssets.
- [x] Perfil TextAsset JSON con UnityPy.
- [x] Adaptador para TSV cifrado de Holy Knight Ricca.
- [x] Detección automática inicial.
- [x] Informes detallados JSON/CSV de validación.

## M1 — Registro de adaptadores — completado

Objetivo: eliminar la dependencia de `if/elif` por extractor en `pipeline.py`.

- [x] Descriptor común de adaptador.
- [x] Registro determinista por ID/version.
- [x] Capacidades y limitaciones serializables.
- [x] Compatibilidad hacia atrás con manifiestos actuales.
- [x] Tests de registro y resolución.

Evidencia: los tres adaptadores existentes se resuelven mediante el registro y la suite completa pasa con 39 tests.

## M2 — Detector con candidatos y evidencia

- [ ] Inventario de archivos por tipo.
- [ ] Firmas de framework.
- [ ] Candidatos con confianza, evidencia y limitaciones.
- [ ] Niveles `automatic`, `assisted` e `investigation`.
- [ ] UI para elegir entre candidatos cuando haya ambigüedad.
- [ ] CLI `diagnose`.

## M3 — Addressables / AssetBundles

- [ ] Detección de `StreamingAssets/aa`.
- [ ] Inventario de catálogos y bundles.
- [ ] Inspección read-only con UnityPy.
- [ ] Descubrimiento de TextAssets/JSON/CSV/String Tables.
- [ ] Perfil generado con localizadores.
- [ ] Extracción a IR.
- [ ] Reinyección sobre copia.
- [ ] Verificación de bundles, catálogo y CRC.

El caso de prueba inicial es CIRCLEMATE, pero el adaptador debe basarse en la familia Addressables, no en el nombre del juego.

## M4 — Unity Localization y frameworks

- [ ] Unity Localization/String Tables.
- [ ] Naninovel.
- [ ] Pixel Crushers.
- [ ] 2D Toolkit.
- [ ] Otros frameworks solo cuando exista evidencia y fixture.

Cada framework debe incorporarse como adaptador independiente con tests y limitaciones explícitas.

## M5 — Paquete de investigación

- [ ] `diagnostics/` dentro del proyecto.
- [ ] `problem.md`.
- [ ] `diagnostics.json`.
- [ ] estructura de directorios sanitizada.
- [ ] firmas detectadas.
- [ ] assemblies enumerados sin contenido innecesario.
- [ ] logs sanitizados.
- [ ] guía de API del adaptador.
- [ ] tests esperados.

No incluir por defecto assets completos, traducciones, rutas personales, secretos ni contenido protegido innecesario.

## M6 — Robustez del proyecto

- [ ] Descubrimiento controlado de `*_Data` en un nivel descendiente.
- [ ] Manifiesto con fingerprint de juego/build.
- [ ] Reanudación segura de proyectos existentes.
- [ ] Detección de archivos fuente modificados.
- [ ] Rollback explícito de staging incompleto.
- [ ] Reporte de archivos cambiados y hashes finales.

## M7 — Compatibilidad y distribución

- [ ] Fixtures legales por adaptador.
- [ ] Pruebas con juegos reales accesibles.
- [ ] Checklist de playtesting.
- [ ] Promoción de `experimental` a `supported` solo con evidencia.
- [ ] CI de tests y build.
- [ ] Build portable Windows sin Python.
- [ ] Release reproducible.

## Fuera de prioridad inmediata

- Traducción automática.
- Supabase obligatorio.
- Telemetría automática.
- Cuentas/login.
- Marketplace.
- UI avanzada.
- Dashboard.
- SQLite antes de que el IR JSON sea un límite real.

## Criterio general de avance

Cada milestone debe seguir:

```text
test RED
→ implementación mínima
→ test GREEN
→ suite completa
→ prueba real o fixture reproducible
→ documentación de evidencia
→ commit pequeño
```

No declarar compatibilidad universal. La herramienta debe ser universal en arquitectura y extensible en adaptadores, pero cada formato requiere evidencia propia.
