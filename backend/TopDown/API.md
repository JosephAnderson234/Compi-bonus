# Top-Down — Contrato de API

Parsers **descendentes** para análisis sintáctico. Cada módulo expone `run_analysis(input_data)` con el mismo esquema de **entrada**; la **salida** comparte campos base y añade campos propios del método.

---

## Parsers implementados

| `tipo_parser` | Módulo | Función | Clase interna |
|---------------|--------|---------|---------------|
| `LL1` | `ll1_parser.py` | `run_analysis(input_data)` | `LL1Parser` |
| `RD` / `DR` | `dr_parser.py` | `run_analysis(input_data)` | `RecursiveDescentParser` |

```python
import sys
sys.path.insert(0, "backend/TopDown")

from ll1_parser import run_analysis as analyze_ll1
from dr_parser import run_analysis as analyze_rd
```

### Enrutamiento sugerido (backend)

```python
PARSERS = {
    "LL1": analyze_ll1,
    "RD":  analyze_rd,
    "DR":  analyze_rd,   # alias
}

def dispatch(request: dict) -> dict:
    tipo = request.get("tipo_parser", "LL1").upper()
  # normalizar alias
    if tipo == "DR":
        tipo = "RD"
    fn = PARSERS.get(tipo)
    if fn is None:
        return {"error": f"tipo_parser '{tipo}' no soportado"}
    return fn(request)
```

---

## Entrada (`input_data`)

Objeto JSON/dict con **tres claves obligatorias** (todas `str`):

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `gramatica` | `string` | Gramática en texto plano: **una producción por línea**, formato `NT -> alt1 \| alt2 \| ...`. |
| `simbolo_inicial` | `string` | No terminal inicial (debe existir en la gramática). |
| `cadena_entrada` | `string` | Cadena **ya tokenizada**: tokens separados por **un espacio**. El parser añade `$` al final internamente. |

### Campo opcional (router)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `tipo_parser` | `string` | `"LL1"` o `"RD"` / `"DR"` — lo usa el backend para elegir módulo. |

### Formato de la gramática

- Separador de producción: `->`
- Alternativas en la misma línea: `|`
- Símbolos dentro de una alternativa: separados por espacios.
- Líneas vacías o sin `->` se ignoran (LL1) o se omiten (RD).

### Épsilon

| Representación | Uso |
|----------------|-----|
| **`eps`** | Valor canónico en JSON y lógica interna. |
| Alternativa vacía | `A -> b \|` o nada tras el último `\|` → se normaliza a `eps`. |
| `ε`, `epsilon`, `EPS`, … | Solo en **texto de entrada**: se normalizan a `eps` al parsear. |

Ejemplo:

```text
E  -> T E'
E' -> + T E' | eps
T  -> F T'
T' -> * F T' | eps
F  -> ( E ) | id
```

### Ejemplo de request

```json
{
  "gramatica": "E  -> T E'\nE' -> + T E' | eps\nT  -> F T'\nT' -> * F T' | eps\nF  -> ( E ) | id",
  "simbolo_inicial": "E",
  "cadena_entrada": "id + id * id",
  "tipo_parser": "LL1"
}
```

---

## Salida — campos comunes (ambos parsers)

| Campo | Tipo | Siempre | Descripción |
|-------|------|---------|-------------|
| `gramatica_parseable` | `boolean` | Sí | Si la gramática es usable con **ese** método (ver criterio por parser). |
| `cadena_valida` | `boolean` | Sí | Si la cadena pertenece al lenguaje. |
| `mensaje` | `string` | Sí | Resumen legible del resultado o del error. |
| `proceso_paso_a_paso` | `array` | Sí | Traza del análisis; `[]` si se abortó por gramática no parseable (LL1) o no compatible (RD). |

**Importante:** `gramatica_parseable === true` **no implica** `cadena_valida === true`.

---

## `gramatica_parseable` por método

| Parser | `true` cuando | `false` cuando |
|--------|---------------|----------------|
| **LL(1)** | Tabla LL(1) sin conflictos. | Conflictos en `M[NT, t]` y/o recursividad izquierda no resuelta automáticamente. |
| **Descenso recursivo** | Símbolo inicial definido y **sin** recursividad izquierda directa (`A -> A α …`). | NT inicial ausente o recursividad izquierda directa. |

---

## `proceso_paso_a_paso`

### LL(1)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `paso` | `number` | Índice 1-based. |
| `pila` | `string` | Pila con tope a la **derecha** (incluye `$`). |
| `entrada` | `string` | Buffer restante (incluye `$`). |
| `accion` | `string` | Ver ejemplos. |

Valores típicos de `accion`:

- `ACEPTAR`
- `Coincidencia: 'id'`
- `E -> T E'` (producción aplicada)
- `ERROR: ...`

### Descenso recursivo (RD)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `paso` | `number` | Índice 1-based. |
| `accion` | `string` | Descripción (backtracking, match terminal, ACEPTAR, RECHAZAR, expansión NT, etc.). |

**No** incluye `pila` ni `entrada` en cada paso (solo traza narrativa).

---

## Salida específica: LL(1) — `ll1_parser.py`

### Campos adicionales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `conjuntos_first_follow` | `object` | Por cada NT: `{ "FIRST": string[], "FOLLOW": string[] }` (ordenadas). Épsilon = `"eps"`. |
| `construccion_tablas` | `object` | Tabla predictiva LL(1). |
| `sugerencias_transformacion` | `object` | Si la gramática no es LL(1). |

### `construccion_tablas`

```json
{
  "tipo": "LL1",
  "columnas": ["NoTerminal", "id", "+", "*", "(", ")", "$"],
  "filas": [
    { "NoTerminal": "E", "id": "E -> T E'", "$": "E -> T E'" }
  ]
}
```

| Campo | Descripción |
|-------|-------------|
| `columnas` | Primera columna `NoTerminal`; resto = terminales (incl. `$`). |
| `filas` | Una fila por NT. Celda ausente = sin entrada (no usar string vacío). |
| Conflictos en celda | Varias producciones unidas por ` o ` (ej. `E -> E + T o E -> T`). |

### `sugerencias_transformacion`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `requiere_transformacion` | `boolean` | |
| `motivo` | `string` | Causa (conflictos, recursividad izquierda, etc.). |
| `gramatica_sugerida` | `string \| null` | Gramática transformada (multilínea) o `null`. |

Al eliminar recursividad izquierda o factorizar, los **nuevos no terminales** (`A'`, `A''`, …) se nombran con comillas repetidas hasta evitar colisión con NTs, terminales y símbolos en cuerpos ya existentes (p. ej. si `A'` es terminal, el NT auxiliar será `A''`).

Si `gramatica_parseable === false`: `proceso_paso_a_paso` suele ser `[]`, `cadena_valida === false`, pero **sí** se devuelven `conjuntos_first_follow`, `construccion_tablas` (con conflictos) y `sugerencias_transformacion`.

### Respuesta LL(1) — gramática válida, cadena aceptada

```json
{
  "gramatica_parseable": true,
  "cadena_valida": true,
  "mensaje": "Análisis completado exitosamente. La cadena es válida.",
  "conjuntos_first_follow": {
    "E": { "FIRST": ["(", "id"], "FOLLOW": ["$", ")"] },
    "E'": { "FIRST": ["+", "eps"], "FOLLOW": ["$", ")"] }
  },
  "construccion_tablas": {
    "tipo": "LL1",
    "columnas": ["NoTerminal", "(", ")", "*", "+", "id", "$"],
    "filas": []
  },
  "proceso_paso_a_paso": [
    {
      "paso": 1,
      "pila": "E $",
      "entrada": "id + id * id $",
      "accion": "E -> T E'"
    }
  ],
  "sugerencias_transformacion": {
    "requiere_transformacion": false,
    "motivo": "La gramática ya es LL(1) válida.",
    "gramatica_sugerida": null
  }
}
```

### Respuesta LL(1) — gramática no LL(1)

```json
{
  "gramatica_parseable": false,
  "cadena_valida": false,
  "mensaje": "La gramática no es LL(1). Se aplican transformaciones automáticas. La simulación de la cadena fue abortada.",
  "conjuntos_first_follow": {},
  "construccion_tablas": { "tipo": "LL1", "columnas": [], "filas": [] },
  "proceso_paso_a_paso": [],
  "sugerencias_transformacion": {
    "requiere_transformacion": true,
    "motivo": "La gramática NO es LL(1) debido a: ...",
    "gramatica_sugerida": "E -> T E'\n..."
  }
}
```

---

## Salida específica: Descenso recursivo — `dr_parser.py`

### Campos adicionales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `arbol_derivacion` | `object \| null` | Árbol de la derivación exitosa; `null` si rechazo o gramática no compatible. |

**No** incluye `conjuntos_first_follow` ni `construccion_tablas`.

### Nodo del árbol (`arbol_derivacion`)

```json
{
  "name": "E",
  "children": [
    { "name": "T", "children": [] },
    { "name": "eps", "children": [] }
  ]
}
```

| Campo | Descripción |
|-------|-------------|
| `name` | NT, terminal (`id`, `+`, …) o `"eps"`. |
| `children` | Subárboles; `[]` en hojas y en nodo épsilon. |

### Respuesta RD — éxito

```json
{
  "gramatica_parseable": true,
  "cadena_valida": true,
  "mensaje": "Cadena analizada correctamente por Descenso Recursivo.",
  "proceso_paso_a_paso": [
    { "paso": 1, "accion": "Expandir E" },
    { "paso": 2, "accion": "ACEPTAR: Cadena válida." }
  ],
  "arbol_derivacion": { "name": "E", "children": [] }
}
```

### Respuesta RD — gramática incompatible

```json
{
  "gramatica_parseable": false,
  "cadena_valida": false,
  "mensaje": "La gramatica tiene recursividad izquierda directa; no es compatible con descenso recursivo.",
  "proceso_paso_a_paso": [],
  "arbol_derivacion": null
}
```

---

## Comparativa Top-Down

| Aspecto | LL(1) | Descenso recursivo |
|---------|-------|---------------------|
| Tabla predictiva | Sí (`construccion_tablas`) | No |
| FIRST/FOLLOW | Sí | No |
| Árbol de derivación | No | Sí (`arbol_derivacion`) |
| `pila` / `entrada` en pasos | Sí | No |
| Recursividad izquierda | Sugiere transformación | Rechaza gramática |
| `gramatica_parseable` | Sí | Sí |

---

## Integración frontend ↔ backend

### 1. Request

Enviar `gramatica`, `simbolo_inicial`, `cadena_entrada` y `tipo_parser` (`LL1` o `RD`).

### 2. Tokenización

- Tokens separados por espacio.
- **No** enviar `$` en `cadena_entrada`.

### 3. UI recomendada

| Badge / estado | Campo |
|----------------|-------|
| Gramática OK para el método | `gramatica_parseable` |
| Cadena aceptada | `cadena_valida` |
| Tabla LL(1) | `construccion_tablas` (filas = NT, columnas = terminales) |
| FIRST/FOLLOW | `conjuntos_first_follow` |
| Árbol (RD) | `arbol_derivacion` (componente árbol recursivo sobre `name`/`children`) |
| Traza | `proceso_paso_a_paso` |
| Sugerencia si no es LL(1) | `sugerencias_transformacion.gramatica_sugerida` |

### 4. Tabla LL(1) en frontend

- Encabezados: `construccion_tablas.columnas`
- Filas: `construccion_tablas.filas[i][columna]`
- Celda vacía: clave omitida en el objeto fila

### 5. Árbol RD en frontend

Render recursivo:

```text
function renderNode(n):
  if n.children.length == 0: return n.name
  return n.name + "(" + join(renderNode(c) for c in n.children) + ")"
```

### 6. Épsilon

- JSON: `eps`
- UI: opcional mostrar `ε`

### 7. Errores y estados vacíos

| Condición | Comportamiento UI |
|-----------|-------------------|
| `gramatica_parseable === false` | No esperar simulación útil; mostrar `mensaje` y sugerencias (LL1) |
| `proceso_paso_a_paso.length === 0` | Sin traza paso a paso |
| `cadena_valida === false` y gramática OK | Mostrar traza hasta el error |

### 8. Tests locales

```bash
cd backend/test
python test_ll1.py
python test_rd.py
python test_grammar_symbols.py   # colisiones de nombres (opcional, requiere asserts manuales)
```

---

## Contrato unificado con Bottom-Up (referencia)

El proyecto comparte entrada con parsers LR:

```json
{
  "gramatica": "...",
  "simbolo_inicial": "E",
  "cadena_entrada": "id + id",
  "tipo_parser": "LL1"
}
```

Valores de `tipo_parser` en el proyecto completo:

| Valor | Carpeta | Módulo |
|-------|---------|--------|
| `LL1` | TopDown | `ll1_parser` |
| `RD`, `DR` | TopDown | `dr_parser` |
| `LR0` | BottomUp | `lr0_parser` |
| `SLR1` | BottomUp | `slr1_parser` |
| `LR1` | BottomUp | `lr1_parser` |
| `LALR1` | BottomUp | `lalr1_parser` |

Ver `backend/BottomUp/API.md` para salida LR (`afn_clausura`, tablas shift-reduce, etc.).

---

## Constantes

| Constante | Valor |
|-----------|--------|
| Épsilon (JSON) | `eps` |
| Fin de entrada | `$` |

---

## Estructura de archivos

```
backend/
├── grammar_symbols.py   # fresh_prime_name, symbols_in_grammar (compartido con Bottom-Up)
└── TopDown/
    ├── ll1_parser.py
    ├── dr_parser.py
    └── API.md    # este documento
```
