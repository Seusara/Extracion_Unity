# Soporte Naninovel experimental

## Alcance

`naninovel-addressables` soporta experimentalmente scripts Naninovel serializados
como `MonoBehaviour` dentro de bundles Addressables de juegos Unity Mono.

El adaptador no depende del nombre del juego. Detecta y conserva:

- ruta relativa del bundle;
- asset dentro del bundle;
- `path_id` del objeto;
- `entry_index` del registro;
- campo serializado;
- texto original y traducción en el Translation IR.

## Flujo validado

La evidencia E2E se obtuvo sobre una copia completa de BOXMAN, que funciona como
fixture externa de validación y no se distribuye con el repositorio:

```text
extract
→ export CSV
→ modificar una entrada por ID estable
→ import CSV
→ validate
→ snapshot original
→ backup
→ staging
→ write_typetree
→ rebuild
→ reopen
→ verificar contra entry["translated_text"]
→ output separado
```

Caso validado:

```text
Dialogue Here
→ PRUEBA_UNITYTRANSLATOR_12345
```

La traducción más larga fue leída del bundle reabierto y comparada directamente
con `entry["translated_text"]`. No se utilizó una extracción posterior para
redefinir `original_text`.

También se verificó una entrada no relacionada y los conteos de objetos del
bundle antes y después.

## Tests reproducibles del repositorio

Los tests no contienen assets de juegos con copyright. Usan fixtures temporales y
entornos simulados para cubrir el contrato determinista:

- traducciones más largas, más cortas e iguales;
- localizadores incorrectos (`object_not_found`, `entry_not_found`,
  `field_not_found`, `asset_not_found`, `expected_text_mismatch`);
- `text_mismatch` controlado y errores inesperados (`verification_error`);
- propagación del `translated_text` desde el IR;
- propagación de errores del inyector;
- preservación de registros no relacionados;
- persistencia de cambios en bundles con más de un objeto traducido;
- cierre de handles `dnfile` en Windows, incluyendo DLLs que fallan al parsear;
- snapshots y backups con SHA-256 idéntico al origen.

## Diagnóstico de cobertura

- Si un registro serializado no se puede parsear (tipo desconocido o DLL
  corrupta), ya no se descarta en silencio: `extract` escribe
  `logs/naninovel-unparsed-types.json` con el conteo de tipos saltados y los
  ensamblados que fallaron al leerse, y lo deja en el log del pipeline.
- `naninovel_audit.audit_command_coverage(game_root)` recorre todos los
  bundles y reporta campos de comandos Naninovel que parecen texto pero no
  tienen regla en `TEXT_FIELDS` — evidencia para decidir si conviene ampliar
  la allowlist en un juego nuevo, sin adivinar.
- `unity-translator init --auto` genera el perfil `naninovel-addressables`
  automáticamente (vía `detect_profile`) en vez de requerir un JSON escrito a
  mano.

## CRC de catálogo Addressables

Unity carga bundles locales con `AssetBundle.LoadFromFileAsync(path, crc)`,
donde `crc` sale del `AssetBundleRequestOptions` guardado en el catálogo. Un
CRC distinto de cero que ya no coincide con el bundle reescrito hace que
Addressables rechace cargarlo. `inject_bundle()` ahora localiza el/los
`catalog*.json` bajo `StreamingAssets/aa`, ubica la entrada de ese bundle vía
`m_EntryDataString`/`m_ExtraDataString`, y pone su `m_Crc` en 0 — sin tocar
ningún otro byte del catálogo (el reemplazo preserva el largo exacto del
JSON serializado, así que ninguna otra entrada se desplaza).

El layout binario implementado (`src/unity_translator/addressables_catalog.py`)
sale del código fuente real de `com.unity.addressables`
(`Runtime/Utility/SerializationUtilities.cs`, `Runtime/ResourceLocators/JsonContentCatalogData.cs`,
`Runtime/ResourceManager/ResourceProviders/AssetBundleProvider.cs`), no de
memoria — pero **no se validó todavía contra un catálogo generado por un
build real de Unity**. Los tests cubren round-trip contra un catálogo
sintético construido con el mismo layout.

Catálogos binarios (`catalog*.bin`, un formato completamente distinto
`BinaryStorageBuffer`) no están soportados: si solo hay un `.bin`,
`inject_bundle()` falla explícitamente en vez de arriesgarse a dejar un CRC
sin verificar. Si un bundle no aparece en ningún catálogo, se deja como
está (no todo bundle Addressables pasa por verificación de CRC).

## Estado de compatibilidad

```text
support: experimental
```

Esto significa que la escritura y verificación estructural están validadas, pero
no implica compatibilidad universal con todos los juegos Naninovel.

Siguen pendientes para `supported`:

1. Validar la neutralización de CRC (arriba) contra un catálogo `.json`
   generado por un build real de Addressables, no solo contra el sintético
   de los tests.
2. Soporte (o detección más útil) para catálogos binarios (`catalog*.bin`).
3. Playtesting visual de una ruta jugable que solicite el script traducido.
4. Segundo juego real de la misma familia.
5. Fixture binaria legal y pequeña, si se consigue una fuente redistribuible.

## Restricciones

- No modificar la instalación original.
- No reemplazar arrays completos cuando solo se traduce una entrada.
- No considerar éxito si falla reopen o verificación.
- No declarar que una nueva extracción conserva el `original_text` después de
  inyectar; la verificación debe usar el IR original.
- El único cambio automático que se permite en catálogos Addressables es
  poner en 0 el `m_Crc` del bundle recién reescrito, respaldado por el
  código fuente real de Addressables (ver arriba) — no una heurística ni una
  regla específica de un juego. Cualquier otro cambio al catálogo sigue
  fuera de alcance sin evidencia específica nueva.
