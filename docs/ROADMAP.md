# Roadmap de UnityTranslator

## Estado base — completado

- [x] Core offline y determinista.
- [x] CLI y GUI sobre el mismo pipeline.
- [x] Translation IR JSON.
- [x] CSV estricto con round-trip.
- [x] Validación de placeholders, tags, escapes y hashes.
- [x] Backups, staging, builds separados y restore.
- [x] Perfiles CSV, TextAsset JSON y TSV cifrado.
- [x] Detección automática inicial.
- [x] Informes detallados JSON/CSV de validación.

## M1 — Registro de adaptadores — completado

- [x] Descriptor común de adaptador.
- [x] Registro determinista por ID/version.
- [x] Capacidades y limitaciones serializables.
- [x] Compatibilidad hacia atrás con manifiestos actuales.
- [x] Tests de registro y resolución.

Evidencia: los adaptadores existentes se resuelven mediante el registro y la suite pasó con 39 tests al cerrar M1.

## M2 — Detector con candidatos y evidencia — completado

- [x] Inventario de archivos por tipo.
- [x] Firmas de framework.
- [x] Candidatos con confianza, evidencia y limitaciones.
- [x] Niveles `automatic`, `assisted` e `investigation`.
- [x] UI para visualizar candidatos y limitaciones.
- [x] CLI `analyze` con salida detallada.
- [x] Descubrimiento controlado de `*_Data` en un nivel descendiente.

Evidencia: 9 tests M2 cubren candidatos fuertes/múltiples, desconocidos, falsos positivos, evidencia insuficiente, niveles, ambigüedad, descubrimiento anidado y sanitización.

## M3 — Investigation Package — completado

- [x] `AI_CONTEXT/` local sanitizado y `AI_CONTEXT.zip`.
- [x] README, problem statement y perfil derivado de M2.
- [x] Candidatos y firmas preservados.
- [x] Árbol acotado con marca de truncamiento.
- [x] Assemblies por nombre, sin contenido de DLL.
- [x] Logs sanitizados.
- [x] API de adaptadores, protocolo de investigación y tests esperados.
- [x] CLI `diagnose` manual para cualquier nivel.
- [x] Botón mínimo equivalente en GUI.
- [x] Exclusión de assets, ejecutables, secretos, saves y rutas personales.

Evidencia: 4 tests específicos cubren generación, sanitización, exclusiones, truncamiento, contenido permitido del ZIP y CLI. Suite total verificada con 52 tests.

M3 no implementa extracción/reinyección de Addressables o AssetBundles, no conecta Supabase y no ejecuta IA dentro de la aplicación.

## M4 — Addressables / AssetBundles

- [ ] Detección e inventario de catálogos y bundles ya está disponible en M2.
- [ ] Inspección read-only con UnityPy.
- [ ] Descubrimiento de TextAssets/JSON/CSV/String Tables.
- [ ] Perfil generado con localizadores.
- [ ] Extracción a IR.
- [ ] Reinyección sobre copia.
- [ ] Verificación de bundles, catálogo y CRC.

El caso inicial será CIRCLEMATE, pero el adaptador debe basarse en la familia Addressables, nunca en el nombre del juego.

## M5 — Frameworks de texto

- [ ] Unity Localization/String Tables.
- [ ] Naninovel.
- [ ] Pixel Crushers.
- [ ] 2D Toolkit.
- [ ] Otros frameworks solo con evidencia, fixture y tests.

Cada framework debe incorporarse como adaptador independiente con limitaciones explícitas.

## M6 — Robustez del proyecto

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

```text
test RED
→ implementación mínima
→ test GREEN
→ suite completa
→ fixture o prueba real
→ documentación de evidencia
→ commit pequeño
```

No declarar compatibilidad universal. La herramienta debe ser universal en arquitectura y extensible en adaptadores, pero cada formato requiere evidencia propia.
