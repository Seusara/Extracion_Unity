# Guía de uso de Unity Translator

Unity Translator es una aplicación de escritorio para **extraer, editar, validar y reinyectar textos de juegos Unity** sin modificar la instalación original. El flujo funciona offline y genera siempre una copia separada para las pruebas.

> **Estado del soporte:** experimental. Actualmente se soportan perfiles para CSV dentro de `StreamingAssets` y `TextAsset` JSON dentro de archivos Unity. No todos los juegos Unity utilizan las mismas estructuras.

---

## 1. Descargar y abrir la aplicación

### Opción recomendada: ejecutable portable

1. Descarga [`UnityTranslator-0.1.0-windows-x64.zip`](https://github.com/Seusara/Extracion_Unity/releases/download/v0.1.0/UnityTranslator-0.1.0-windows-x64.zip).
2. Extrae el ZIP completo en una carpeta, por ejemplo:

   ```text
   C:\Herramientas\UnityTranslator\
   ```

3. Ejecuta `UnityTranslator.exe`.
4. Si Windows SmartScreen muestra una advertencia, verifica que el archivo provenga del Release oficial y confirma la ejecución. El ejecutable no está firmado digitalmente.
5. La aplicación no requiere Python instalado ni conexión a Internet durante el uso.

El ZIP incluye estos perfiles:

```text
profiles/streamingassets-dialogue.json
profiles/unity-textasset-json.json
profiles/ERICA-TextData.json
```

### Tutorial inicial

Al primer inicio aparece un tutorial textual de cuatro pasos. Puedes:

- avanzar con **Siguiente**;
- volver con **Anterior**;
- omitirlo con **Omitir**;
- cerrarlo con **Listo**;
- volver a abrirlo desde **Ver tutorial** o pulsando `F1`.

La opción **Mostrar tutorial al iniciar** permite decidir si debe volver a aparecer automáticamente.

---

## 2. Preparar las carpetas

Antes de usar la aplicación, identifica estas rutas:

### Carpeta original del juego

Es la carpeta que contiene el ejecutable del juego y su carpeta `*_Data`, por ejemplo:

```text
C:\Juegos\MiJuego\
├── MiJuego.exe
├── MiJuego_Data\
└── UnityPlayer.dll
```

Selecciona la carpeta raíz del juego, no solamente `MiJuego_Data`.

### Carpeta de trabajo

Debe ser una carpeta distinta de la instalación original. Por ejemplo:

```text
C:\Traducciones\MiJuego-es\
```

La aplicación guardará allí:

```text
C:\Traducciones\MiJuego-es\
├── manifest.json
├── originals\
├── extracted\
├── backups\
└── builds\
```

**No uses la carpeta original como carpeta de trabajo.** Aunque el pipeline protege la instalación fuente, mantenerlas separadas evita confusiones y facilita restaurar o eliminar el trabajo.

### Carpeta del ejecutable portable

No es obligatorio colocar el programa dentro de la carpeta del juego. Es preferible mantenerlo separado, por ejemplo:

```text
C:\Herramientas\UnityTranslator\UnityTranslator.exe
```

---

## 3. Elegir el perfil correcto

El perfil le indica a la aplicación dónde están los textos y cómo leerlos. No se debe elegir un perfil al azar: primero analiza el juego y revisa su estructura.

### Perfil CSV en StreamingAssets

Usa `streamingassets-dialogue.json` cuando los textos estén en un CSV dentro de:

```text
<Juego>_Data\StreamingAssets\
```

El perfil incluido busca `dialogue.csv`, espera una fila de encabezado y extrae la columna configurada. Los índices de columna son **base cero**: `0` es la primera columna, `1` la segunda, etc.

Perfil incluido:

```json
{
  "extractor": "streamingassets-csv",
  "files": [
    {
      "glob": "dialogue.csv",
      "columns": [1],
      "header": true,
      "encoding": "utf-8-sig",
      "delimiter": ","
    }
  ]
}
```

### Perfil TextAsset JSON

Usa `unity-textasset-json.json` cuando los textos estén dentro de un `TextAsset` JSON en un archivo Unity serializado.

```json
{
  "extractor": "unity-textasset-json",
  "asset_file": "sharedassets0.assets",
  "textasset": {
    "name": "TextData",
    "path_id": 554
  },
  "list_key": "texts",
  "id_field": "dataID",
  "text_field": "ENG"
}
```

### Perfil de ERICA

Para la versión probada de **ERICA Knight of the Sun 0.1.9.2**, usa:

```text
profiles/ERICA-TextData.json
```

Ese perfil apunta a `sharedassets0.assets`, al `TextAsset` `TextData` y al `path_id` `554`.

Un perfil funciona solamente si coincide con la estructura exacta del juego. Si otro juego utiliza otro archivo, otro `path_id` o distintas claves JSON, debes crear o ajustar un perfil específico.

---

## 4. Flujo completo desde la interfaz gráfica

La interfaz tiene desplazamiento vertical. Puedes usar:

- la scrollbar lateral;
- la rueda del mouse;
- `F1` para abrir la ayuda.

### Paso 1: seleccionar las rutas

En la sección **Proyecto**, completa:

1. **Juego:** selecciona la carpeta raíz de la instalación original.
2. **Proyecto:** selecciona o escribe una carpeta de trabajo vacía o dedicada.
3. **Perfil:** selecciona el archivo JSON adecuado.
4. **CSV:** selecciona la ruta donde se guardará o desde donde se importará el CSV.

Puedes escribir las rutas manualmente o usar **Elegir…**.

### Paso 2: analizar el juego

Pulsa **Analizar**.

La aplicación muestra en el registro:

- si detectó una instalación Unity;
- versión de Unity, cuando está disponible;
- runtime, por ejemplo Mono o IL2CPP;
- presencia de `StreamingAssets`;
- presencia de Addressables;
- compatibilidad estimada.

El análisis no extrae ni modifica archivos. Si el resultado no corresponde al juego elegido, detén el flujo y revisa la ruta.

### Paso 3: crear el proyecto de trabajo

Pulsa **Crear proyecto**.

La aplicación lee el perfil JSON y crea el manifiesto del proyecto de traducción. Este manifiesto conserva la configuración usada para que las operaciones posteriores sean reproducibles.

Si aparece un error:

- verifica que la ruta del juego sea correcta;
- verifica que la ruta del proyecto sea escribible;
- verifica que el perfil sea un JSON válido;
- verifica que el perfil corresponda al juego.

### Paso 4: extraer los textos

Pulsa **Extraer textos**.

La aplicación analiza el juego según el perfil y guarda una representación de trabajo dentro de la carpeta del proyecto. Los archivos originales utilizados para comparar y reconstruir se conservan en `originals/`.

El registro indica cuántas cadenas se extrajeron. Si devuelve cero cadenas o falla, normalmente el problema está en el perfil, el archivo indicado o la ruta del juego.

### Paso 5: exportar a CSV

Indica una ruta en el campo **CSV**, por ejemplo:

```text
C:\Traducciones\MiJuego-es\mi-juego-es.csv
```

Pulsa **Exportar CSV**.

El CSV contiene, entre otros datos, los campos necesarios para conservar la identidad de cada entrada y editar la traducción. Edita solamente los campos de traducción y la marca de vacío intencional.

No cambies:

- los identificadores;
- las rutas de archivo;
- los índices de objeto;
- el texto original;
- la estructura o los nombres de columnas.

Guarda el CSV usando una codificación compatible, preferentemente UTF-8.

### Paso 6: editar las traducciones

Puedes editar el CSV con Excel, LibreOffice, Google Sheets o un editor de texto.

Recomendaciones:

- conserva el encabezado;
- conserva el delimitador original;
- no elimines filas;
- no dupliques identificadores;
- conserva saltos de línea y marcadores especiales;
- revisa comillas y caracteres Unicode;
- no traduzcas nombres técnicos, variables o claves salvo que el perfil lo indique.

También puedes pulsar **Abrir editor manual** desde la interfaz después de haber creado y extraído el proyecto.

El editor permite:

- buscar texto;
- filtrar por **Todas**;
- filtrar por **Sin traducir**;
- filtrar por **Traducidas**;
- filtrar por **Vacías intencionales**;
- seleccionar una fila;
- editar su traducción;
- marcar una traducción como vacía intencional;
- guardar el cambio.

El editor guarda la modificación en el proyecto de trabajo, no en el juego original.

### Paso 7: importar el CSV

Después de editar y guardar el CSV:

1. Selecciona la ruta del CSV en el campo **CSV**.
2. Pulsa **Importar CSV**.
3. Revisa el registro:

   ```text
   Importadas: ... | Pendientes: ... | Vacías intencionales: ...
   ```

Si hay muchas entradas pendientes, revisa el CSV antes de continuar.

### Paso 8: validar

Pulsa **Validar traducciones**.

La validación busca problemas como:

- traducciones pendientes;
- textos vacíos no marcados como intencionales;
- incompatibilidades estructurales;
- etiquetas o atributos alterados;
- posibles problemas que pueden romper la reinyección.

No continúes a la generación si aparecen errores. Las advertencias requieren revisión, aunque no siempre bloquean la generación.

### Paso 9: generar la copia traducida

Cuando la validación sea aceptable, pulsa **Generar copia traducida**.

La aplicación:

1. crea un backup antes de modificar el contenido de trabajo;
2. copia el juego a una carpeta separada;
3. aplica las traducciones a esa copia;
4. verifica la estructura resultante;
5. actualiza la ruta mostrada en **Resultado: Copia traducida**.

La salida queda en una ruta similar a:

```text
C:\Traducciones\MiJuego-es\builds\20260822T163430421080Z\game\
```

La instalación original no se modifica.

### Paso 10: probar el resultado

En la sección **Resultado: Copia traducida** encontrarás:

- **Abrir carpeta:** abre la carpeta del último build generado.
- **Ejecutar copia:** busca y ejecuta el `.exe` dentro del build separado.
- **Restaurar:** restaura los archivos respaldados dentro de la copia.

Prueba siempre el juego generado, no el ejecutable original.

### Paso 11: restaurar el último build

Pulsa **Restaurar** y confirma el diálogo.

La operación restaura los archivos respaldados antes de la última inyección dentro de la copia de trabajo/build. El juego original no se modifica.

Usa esta opción si necesitas volver al estado anterior de la copia traducida. Si quieres conservar varias versiones, no borres las carpetas antiguas de `backups/` y `builds/`.

---

## 5. Ubicación de resultados y backups

Dentro de la carpeta de trabajo se generan estas áreas:

### `manifest.json`

Contiene la configuración del proyecto y el perfil utilizado.

### `originals/`

Conserva copias de los archivos originales relevantes para poder comparar y reconstruir.

### `extracted/`

Contiene los datos extraídos y la representación editable.

### `backups/`

Contiene snapshots creados antes de la inyección. Cada backup se identifica por una marca temporal.

### `builds/`

Contiene las copias separadas del juego que se pueden ejecutar y probar.

No borres estas carpetas mientras necesites restaurar o auditar el trabajo.

---

## 6. Flujo equivalente por línea de comandos

Si tienes Python instalado y ejecutaste `pip install -e .`, puedes usar el CLI.

### Analizar

```bash
unity-translator analyze "C:/Juegos/MiJuego"
```

Para obtener JSON:

```bash
unity-translator analyze "C:/Juegos/MiJuego" --json
```

### Crear el proyecto

```bash
unity-translator init \
  "C:/Juegos/MiJuego" \
  "C:/Traducciones/MiJuego-es" \
  --profile "C:/Herramientas/UnityTranslator/profiles/streamingassets-dialogue.json"
```

### Extraer

```bash
unity-translator extract "C:/Traducciones/MiJuego-es"
```

### Exportar CSV

```bash
unity-translator export \
  "C:/Traducciones/MiJuego-es" \
  "C:/Traducciones/MiJuego-es/textos.csv"
```

### Importar CSV

```bash
unity-translator import \
  "C:/Traducciones/MiJuego-es" \
  "C:/Traducciones/MiJuego-es/textos.csv"
```

### Validar

```bash
unity-translator validate "C:/Traducciones/MiJuego-es"
```

Para obtener el informe en JSON:

```bash
unity-translator validate "C:/Traducciones/MiJuego-es" --json
```

### Generar la copia

```bash
unity-translator inject "C:/Traducciones/MiJuego-es"
```

### Restaurar manualmente

El CLI necesita el proyecto, el nombre del backup y un destino de copia:

```bash
unity-translator restore \
  "C:/Traducciones/MiJuego-es" \
  "20260822T163430421080Z" \
  "C:/Traducciones/MiJuego-es/builds/prueba/game"
```

La interfaz gráfica simplifica esta última operación usando **Restaurar**, que trabaja sobre el último build detectado.

---

## 7. Problemas frecuentes

### “No se detecta un juego Unity”

- Seleccionaste una subcarpeta en vez de la raíz.
- El juego utiliza una estructura no soportada.
- La instalación está incompleta.
- El juego no es un build Unity compatible con el analizador actual.

### “No se encuentran textos”

- El perfil no corresponde al juego.
- El `asset_file` es incorrecto.
- El `path_id` no coincide.
- El nombre del `TextAsset` o las claves JSON son diferentes.
- El CSV no está dentro de la ruta indicada por el perfil.

### “El CSV no se puede importar”

- Se modificó el encabezado.
- Se eliminaron columnas o filas.
- Se cambió el delimitador.
- Se guardó con una codificación incompatible.
- Se alteraron identificadores.
- Se añadieron comillas o saltos de línea sin respetar el formato CSV.

### “La validación muestra errores”

No generes la copia todavía. Revisa el registro y corrige primero el CSV o el editor manual. Las advertencias pueden ser revisables, pero los errores indican que la reinyección no es segura.

### “No se puede ejecutar la copia”

- Todavía no se generó ningún build.
- La copia no contiene un ejecutable detectable.
- El build fue movido manualmente.
- El juego requiere archivos adicionales que no se copiaron correctamente.

Usa **Abrir carpeta** para verificar qué contiene el último build.

### “La aplicación muestra una advertencia de Windows”

El ejecutable es portable, pero no está firmado digitalmente. Comprueba que lo descargaste desde el Release oficial antes de permitir su ejecución.

---

## 8. Reglas de seguridad del flujo

1. Conserva una copia intacta del juego original.
2. Trabaja siempre en una carpeta de proyecto separada.
3. Ejecuta solamente el build generado para las pruebas.
4. No sobrescribas manualmente la instalación fuente.
5. No borres `backups/` hasta terminar las pruebas.
6. Valida antes de inyectar.
7. Conserva el CSV original editado para poder repetir el proceso.
8. Si el juego utiliza DRM, anti-cheat o protección de integridad, no intentes modificar la instalación original.

---

## 9. Limitaciones actuales

- La interfaz está disponible en español.
- El soporte de extracción depende de perfiles explícitos.
- Actualmente se soportan CSV en `StreamingAssets` y `TextAsset` JSON.
- MonoBehaviour custom y otros formatos serializados requieren soporte adicional.
- La compatibilidad es experimental hasta completar pruebas con más juegos reales.
- El ejecutable portable es Windows x64.
