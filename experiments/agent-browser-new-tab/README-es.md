# Primera petición de una pestaña nueva en agent-browser

Prueba automatizada local realizada el **10 de septiembre de 2026**, relacionada con el [PR #1777](https://github.com/vercel-labs/agent-browser/pull/1777). Se compararon los binarios oficiales **0.36.0 y 0.37.0** con el mismo Chromium de pruebas, perfiles vacíos y un servidor HTTP en `127.0.0.1`.

Se configuraron `User-Agent: ab-tab-new-test/1.0` y `X-Global: global`, se comprobó la pestaña principal y se abrió otra con `tab new <url>`. El servidor guardó el primer GET de cada ruta **antes de responder**, sin recargar la página.

| Primer GET observado | 0.36.0 | 0.37.0 |
|---|---|---|
| Pestaña principal: User-Agent | Personalizado | Personalizado |
| Pestaña principal: X-Global | `global` | `global` |
| Pestaña nueva: User-Agent | Predeterminado de Chromium | Personalizado |
| Pestaña nueva: X-Global | Ausente | `global` |

El fallo aparece en 0.36.0 y no aparece en 0.37.0 en este caso. La variante de script incluida se verificó de 07:14:44 a 07:14:51 UTC: **20 comandos correctos, 6,118 segundos**. Una comprobación posterior confirmó cero procesos propios restantes y el puerto cerrado. Los datos concretos están en [resultado-resumen.json](resultado-resumen.json).

## Repetir la prueba

Requisitos: **macOS con Apple Silicon**, Python 3.9 o posterior, `curl` y un ejecutable de **Chromium de pruebas** ya instalado, separado del navegador personal. La ejecución comprobada usó Python 3.9.13 y Chromium 145.0.7632.6. Los binarios incluidos en las descargas son Darwin arm64; otras plataformas quedan fuera de esta receta.

1. Guarda [reproduce.py](reproduce.py) en una carpeta de trabajo vacía y abre una terminal en esa carpeta.
2. Define `CHROMIUM_PRUEBAS` con la ruta al **ejecutable** de tu Chromium de pruebas. Si es una aplicación de macOS, la ruta termina dentro de `Contents/MacOS`, no en `.app`.
3. Ejecuta:

```sh
python3 reproduce.py --chromium-path "$CHROMIUM_PRUEBAS" --download --seconds 240
```

El script descarga únicamente los dos binarios oficiales si faltan, verifica sus SHA-256 antes de ejecutarlos y crea configuración `{}`, perfiles nuevos, sesiones y sockets propios. Conserva HOME sin cambiarlo, elimina las variables heredadas de agent-browser y desactiva auto-connect. Todas las páginas que abre pertenecen al servidor loopback y contienen JSON sintético.

Al terminar imprime `reproduced` si se cumplen los controles y el contraste esperado. Guarda un directorio `run-*` y `latest-results.json` con peticiones y comandos para diagnosticar también resultados distintos o fallos. Los registros generados en tu equipo pueden contener sus rutas locales; revisa esos archivos antes de compartirlos. El paquete presente contiene únicamente estos tres archivos, sin binarios, perfiles ni logs completos.

La primera descarga requiere conexión a GitHub. El sistema debe permitir abrir un servidor loopback y lanzar Chromium. Si impide ejecutar un binario o muestra una advertencia, el script no incluye mecanismos para eludirla. No instala dependencias globales ni descarga un navegador.

## Binarios y fuentes

| Versión | SHA-256 esperado y verificado |
|---|---|
| [0.36.0](https://github.com/vercel-labs/agent-browser/releases/tag/v0.36.0) | `b2106ab39db0838e7b1772f7f26f760518de56d09053150c56f9dddf15af997d` |
| [0.37.0](https://github.com/vercel-labs/agent-browser/releases/tag/v0.37.0) | `da5a2b4ef7be8ba279b1258c542c33877f480b1951d0d94de607fc1528edd380` |

Asset en ambos casos: `agent-browser-darwin-arm64`. Commits de los tags: 0.36.0 → `eb05921bad874cd2a1b4fa5d1149f1ed26576cae`; 0.37.0 → `471ab3852b47b98847f1d9c855c272bb62d0d50b`.

El [PR #1777](https://github.com/vercel-labs/agent-browser/pull/1777), merge `219c47a9dab1776f320d11e66ce934fd239b2cb7`, cambia la aplicación de los ajustes de sesión al crear pestañas. Incluye el test oficial [`e2e_tab_new_inherits_user_agent_and_headers`](https://github.com/vercel-labs/agent-browser/blob/219c47a9dab1776f320d11e66ce934fd239b2cb7/cli/src/native/e2e_tests.rs#L7907). Aquí se condujo el CLI público con un servidor propio; no se ejecutó la suite Rust.

El script distribuido recibe la ruta de Chromium como argumento. Es una copia exacta de la variante parametrizada que se ejecutó y verificó, con SHA-256 `18f29588ca88295ca3af5068f97bff216b2076aa8dee282394f1f200593c81c4`. La primera reproducción usó una ruta fija local; esa versión no se incluye.

## Alcance de la evidencia

Se comparan dos releases completas, con otros cambios entre ellas. El resultado es coherente con el PR; la comparación por sí sola no aísla un único commit ni establece cuándo se introdujo el fallo. Se probaron dos campos de la primera petición, `tab new <url>`, un Chromium y HTTP local. No se validaron producción, cuentas externas, otros navegadores, init scripts ni todas las preferencias de sesión. No hubo captura exhaustiva del tráfico de fondo del navegador.

Durante la preparación se conservaron un intento bloqueado por el sandbox y otro cuyo control de user-agent era inválido porque el primer runner omitía ese flag en las llamadas posteriores. Se corrigió manteniendo constantes los flags y se repitió con éxito; la variante compartible volvió a pasar. La prueba fue automatizada. No se publicó contenido ni se utilizó ninguna cuenta personal.
