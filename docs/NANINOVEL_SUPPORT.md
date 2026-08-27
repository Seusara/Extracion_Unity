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
- localizadores incorrectos;
- `text_mismatch` controlado;
- propagación del `translated_text` desde el IR;
- propagación de errores del inyector;
- preservación de registros no relacionados;
- cierre de handles `dnfile` en Windows;
- snapshots y backups con SHA-256 idéntico al origen.

## Estado de compatibilidad

```text
support: experimental
```

Esto significa que la escritura y verificación estructural están validadas, pero
no implica compatibilidad universal con todos los juegos Naninovel.

Siguen pendientes para `supported`:

1. CRC/catalog de Addressables formalmente decodificado y verificado.
2. Playtesting visual de una ruta jugable que solicite el script traducido.
3. Segundo juego real de la misma familia.
4. Fixture binaria legal y pequeña, si se consigue una fuente redistribuible.

## Restricciones

- No modificar la instalación original.
- No reemplazar arrays completos cuando solo se traduce una entrada.
- No considerar éxito si falla reopen o verificación.
- No declarar que una nueva extracción conserva el `original_text` después de
  inyectar; la verificación debe usar el IR original.
- No cambiar catálogos Addressables automáticamente sin evidencia específica.
