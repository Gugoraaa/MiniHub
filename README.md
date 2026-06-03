# topologiaMiniHub

Topologia para red de MiniHub usando Python y Mininet.

## Requisitos

- Python 3.12 o superior.
- `uv` para administrar el entorno virtual y las dependencias.
- Linux recomendado para ejecutar Mininet.

Verifica que `uv` este instalado:

```bash
uv --version
```

Si no lo tienes instalado:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Despues de instalarlo, cierra y abre la terminal si el comando `uv` todavia no aparece.

## Instalar dependencias

Desde la carpeta del proyecto:

```bash
uv sync
```

Ese comando crea el entorno virtual en `.venv/` e instala los paquetes definidos en `pyproject.toml` y `uv.lock`.

## Activar el entorno virtual

En Linux o macOS:

```bash
source .venv/bin/activate
```

En Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Cuando el entorno este activo, deberias ver `(.venv)` al inicio de la linea de comandos.

Para salir del entorno:

```bash
deactivate
```

## Agregar o quitar paquetes

Para instalar un paquete nuevo en el proyecto:

```bash
uv add nombre-del-paquete
```

Para instalar una dependencia de desarrollo:

```bash
uv add --dev nombre-del-paquete
```

Para quitar un paquete:

```bash
uv remove nombre-del-paquete
```

Despues de agregar o quitar paquetes, sube tambien los cambios de `pyproject.toml` y `uv.lock` al repositorio.

## Correr el servidor

Primero instala las dependencias:

```bash
uv sync
```

Luego ejecuta el proyecto:

```bash
uv run python main.py
```

Si el servidor usa Mininet y pide permisos de administrador, ejecutalo con el Python del entorno virtual:

```bash
sudo .venv/bin/python main.py
```

Para detener el servidor, presiona `Ctrl+C`.

## Flujo recomendado

Cada vez que clones o actualices el proyecto:

```bash
uv sync
source .venv/bin/activate
uv run python main.py
```
