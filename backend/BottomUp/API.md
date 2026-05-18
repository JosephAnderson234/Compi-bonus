# Bottom-Up — Contrato de API

Parsers **ascendentes** (LR). Cada módulo expone `run_analysis(input_data)` con el mismo esquema de **entrada**; la **salida** comparte campos base y añade campos propios del método.

Infraestructura compartida LR(1)/LALR(1): `lr_base.py` (`Grammar`, `LR1Item`, `LRTable`, `run_parser`).

---

## Parsers implementados

| `tipo_parser` | Módulo | Función | Clase interna |
|---------------|--------|---------|---------------|
| `LR0` | `lr0_parser.py` | `run_analysis(input_data)` | `LR0Parser` |
| `SLR1` | `slr1_parser.py` | `run_analysis(input_data)` | `SLR1Parser` |
| `LR1` | `lr1_parser.py` | `run_analysis(input_data)` | `ParserLR1` |
| `LALR1` | `lalr1_parser.py` | `run_analysis(input_data)` | `LALR1Parser` |

```python
import sys
sys.path.insert(0, "backend/BottomUp")  # o usar _paths en tests

from lr0_parser import run_analysis as analyze_lr0
from slr1_parser import run_analysis as analyze_slr1
from lr1_parser import run_analysis as analyze_lr1
from lalr1_parser import run_analysis as analyze_lalr1
```

### Enrutamiento sugerido (backend / `main.py`)

```python
PARSERS = {
    "LR0":   analyze_lr0,
    "SLR1":  analyze_slr1,
    "LR1":   analyze_lr1,
    "LALR1": analyze_lalr1,
}

def dispatch(request: dict) -> dict:
    tipo = request.get("tipo_parser", "LR1").upper()
    fn = PARSERS.get(tipo)
    if fn is None:
        return {"error": f"tipo_parser '{tipo}' no soportado"}
    return fn(request)
```

---

## Entrada (`input_data`)

Objeto JSON/dict. **Tres claves obligatorias** en todos los parsers:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `gramatica` | `string` | Gramática en texto plano: **una producción por línea**, formato `NT -> alt1 \| alt2 \| ...`. |
| `simbolo_inicial` | `string` | No terminal inicial de la gramática **original** (antes de aumentar). |
| `cadena_entrada` | `string` | Cadena **ya tokenizada**: tokens separados por **un espacio**. El parser añade `$` al final. |

### Campo opcional

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `tipo_parser` | `string` | — | Solo usado por el **router** del backend. Cada módulo ignora valores distintos al suyo salvo LR(1) (ver abajo). |

**LR(1):** si se llama `lr1_parser.run_analysis` con `tipo_parser` distinto de `"LR1"`, devuelve `{ "error": "..." }` sin analizar.

### Formato de la gramática

- Separador: `->`
- Alternativas: `|`
- Tokens dentro de una alternativa: separados por espacios.
- Líneas vacías o sin `->` se ignoran.

### Épsilon

| Representación | Uso |
|----------------|-----|
| **`eps`** | Valor canónico en JSON y lógica interna. |
| `ε`, `epsilon`, `EPS`, … | En texto de entrada: se normalizan a `eps` (LR1 vía `Grammar.from_text`). |
| Alternativa vacía | `A -> b \|` o solo `eps` → producción vacía. |

En ítems LR(0): `A -> .` (sin lookahead).  
En reducciones LR(0)/SLR(1): `Reducir ... por A -> eps`.

### Gramática aumentada (automática)

Todos los parsers LR crean internamente una producción `S' -> S` donde `S` es `simbolo_inicial`. **No** hace falta escribirla en `gramatica`.

El nombre del símbolo aumentado se elige como `S'`, `S''`, … (solo comillas repetidas) hasta que no colisione con ningún **no terminal**, **terminal** ni símbolo reservado (`$`, `eps`) ya presente. Ejemplo: si la gramática ya usa el terminal `E'`, el aumentado para `E` será `E''`.

### Ejemplo de request

```json
{
  "gramatica": "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
  "simbolo_inicial": "E",
  "cadena_entrada": "id * id + id",
  "tipo_parser": "LALR1"
}
```

---

## Salida — campos comunes

| Campo | Tipo | Siempre | Descripción |
|-------|------|---------|-------------|
| `cadena_valida` | `boolean` | Sí | `true` si la cadena fue aceptada por shift-reduce. |
| `mensaje` | `string` | Sí | Éxito, rechazo de cadena o descripción de conflictos. |
| `construccion_tablas` | `object` | Sí | Tabla ACTION + GOTO lista para renderizar. |
| `proceso_paso_a_paso` | `array` | Sí | Simulación; `[]` si hay conflictos de tabla y se aborta (LR0/SLR1/LALR1) o si solo hay conflictos sin simulación útil. |
| `afn_clausura` | `object` | Sí* | Colección canónica de ítems (autómata). *Todos los parsers LR actuales lo incluyen. |

**Nota:** Bottom-Up **no** expone `gramatica_parseable` (a diferencia de Top-Down). La gramática es “compatible” con el método si la tabla no tiene conflictos que impidan construirla; en la práctica:

- **LR(0) / SLR(1):** conflictos → `mensaje` menciona conflictos, `proceso_paso_a_paso === []`.
- **LR(1):** puede haber `conflictos` en `construccion_tablas` y aun así simular (según implementación actual).
- **LALR(1):** conflictos de fusión → aborta simulación, `proceso_paso_a_paso === []`.

---

## `afn_clausura` (todos los parsers LR)

Estructura unificada para visualizar el grafo de estados en el frontend. El JSON incluye **todos** los estados (sin truncar); los tests de consola solo muestran los primeros 6.

```json
{
  "tipo": "LR0",
  "estados": [
    {
      "estado": "I0",
      "items": [
        "E' -> . E",
        "E -> . E + T",
        "E -> . T"
      ],
      "transiciones": {
        "(": "I1",
        "E": "I2",
        "id": "I5"
      }
    }
  ]
}
```

| Campo (por estado) | Tipo | Descripción |
|------------------|------|-------------|
| `estado` | `string` | Identificador `I0`, `I1`, … |
| `items` | `string[]` | Ítems con punto (y lookaheads en LR(1)/LALR(1)). |
| `transiciones` | `object` | Mapa `símbolo → "I{n}"` destino. |
| `lr1_fusionados` | `string[]` | **Solo LALR(1):** estados LR(1) que se fusionaron en este estado. |

### Formato de ítems por tipo

| Tipo en `afn_clausura.tipo` | Formato de ítem |
|-----------------------------|-----------------|
| `LR0` | `A -> α . β` (sin lookahead). Cuerpo vacío: `A -> .` |
| `SLR1` | Igual que LR(0) (mismo autómata LR(0)) |
| `LR1` | `A -> α . β , la1/la2` (lookaheads unidos con `/`) |
| `LALR1` | Igual que LR(1) en ítems; transiciones sobre estados fusionados |

### LALR(1) — campo adicional en la raíz

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `afn_lr1` | `object` | Colección LR(1) **completa antes de fusionar** (`tipo: "LR1"`). |
| `lalr_estados` | `object` | Alias de `afn_clausura` (retrocompatibilidad). |

---

## `construccion_tablas`

Formato común para pintar una matriz en el frontend:

```json
{
  "tipo": "SLR1",
  "columnas": ["Estado", "(", ")", "*", "+", "id", "$", "E", "T", "F"],
  "filas": [
    { "Estado": "0", "id": "S5", "E": "3", "$": "ACC" }
  ],
  "conflictos": []
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `tipo` | `string` | `"LR0"`, `"SLR1"`, `"LR1"` o `"LALR1"`. |
| `columnas` | `string[]` | Primera columna siempre `"Estado"`; luego terminales ordenados; en LR(0)/SLR1 también `$` y NTs (GOTO). |
| `filas` | `object[]` | Una fila por estado; claves = nombres de columna. Celda ausente = sin acción. |
| `conflictos` | `array` | **LR(1) y LALR(1)** (vía `LRTable`). Opcional/ausente en LR(0)/SLR(1) (conflictos van en `mensaje`). |

### Convenciones de celda

| Texto en celda | Significado | Parsers |
|----------------|-------------|---------|
| `S{n}` | Shift al estado `n` | Todos |
| `R{k}` | Reduce por producción índice `k` (orden interno `prod_list`) | LR(0), SLR(1) |
| `R(NT -> cuerpo)` | Reduce por producción explícita | LR(1), LALR(1) |
| `ACC` | Aceptar | Todos |
| Número solo (columna NT) | GOTO al estado indicado | LR(0), SLR(1) |
| `n` (string numérica en columna NT) | GOTO | LR(1), LALR(1) |
| `acc1 vs acc2` | Conflicto (en `conflictos[]` en LR1/LALR) | LR(1), LALR(1) |

En LR(0)/SLR(1), celdas con conflicto en tabla pueden mostrarse como `S3 / R2` en la celda y listarse en `mensaje`.

---

## `proceso_paso_a_paso`

Cada elemento:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `paso` | `number` | Índice 1-based. |
| `pila` | `string` | Pila LR: estados y símbolos intercalados (`0 id 5 * 7`). |
| `entrada` | `string` | Tokens restantes incluyendo `$`. |
| `accion` | `string` | Ver ejemplos abajo. |

Valores típicos de `accion`:

- `Desplazar (Shift) al estado 5`
- `Reducir (Reduce) por E -> T` o `... por F -> eps`
- `ACEPTAR` (LR0/SLR1) / `Aceptar (ACC)` (LR1/LALR vía `run_parser`)
- `ERROR: ...` / `Error: no hay accion para 'x' en estado n`

---

## Salida por parser

### LR(0) — `lr0_parser.py`

| Campo extra | Descripción |
|-------------|-------------|
| `afn_clausura.tipo` | `"LR0"` |

**Criterio Reduce:** en todos los terminales del estado (típico LR(0)).  
**Conflictos:** aborta simulación; `afn_clausura` y `construccion_tablas` se devuelven igualmente.

```json
{
  "cadena_valida": true,
  "mensaje": "Análisis sintáctico completado exitosamente sin conflictos LR(0).",
  "afn_clausura": { "tipo": "LR0", "estados": [] },
  "construccion_tablas": { "tipo": "LR0", "columnas": [], "filas": [] },
  "proceso_paso_a_paso": []
}
```

---

### SLR(1) — `slr1_parser.py`

| Campo extra | Descripción |
|-------------|-------------|
| `afn_clausura.tipo` | `"SLR1"` (autómata LR(0) subyacente) |
| `conjuntos_first_follow` | Por NT: `{ "FIRST": string[], "FOLLOW": string[] }` |

**Criterio Reduce:** solo si el terminal ∈ `FOLLOW(A)`.  
**Conflictos:** mensaje multilínea detallado (Shift/Reduce, Reduce/Reduce) + `proceso_paso_a_paso: []`.

```json
{
  "conjuntos_first_follow": {
    "E": { "FIRST": ["(", "id"], "FOLLOW": ["$", ")", "+"] },
    "T": { "FIRST": ["(", "id"], "FOLLOW": ["$", ")", "*", "+"] }
  }
}
```

---

### LR(1) — `lr1_parser.py`

| Campo extra | Descripción |
|-------------|-------------|
| `afn_clausura.tipo` | `"LR1"` |
| `construccion_tablas.conflictos` | Lista `{ estado, simbolo, conflicto }` |

**Criterio Reduce:** solo en lookaheads del ítem LR(1).  
**Conflictos:** registrados en tabla; la simulación puede continuar según la tabla resultante.

**Error de tipo:**

```json
{ "error": "tipo_parser 'LR0' no soportado en lr1_parser (solo LR1)" }
```

---

### LALR(1) — `lalr1_parser.py`

| Campo extra | Descripción |
|-------------|-------------|
| `afn_clausura` | Estados **fusionados** (`tipo: "LALR1"`, con `lr1_fusionados` por estado) |
| `afn_lr1` | Colección LR(1) pre-fusión |
| `lalr_estados` | Alias de `afn_clausura` |
| `construccion_tablas.conflictos` | Conflictos de mesa y/o fusión |

**Flujo:** construye LR(1) → fusiona por núcleo → tabla LALR(1).  
**Conflictos de fusión:** `cadena_valida: false`, `proceso_paso_a_paso: []`, `mensaje` describe estados LR(1) involucrados.

---

## Comparativa rápida

| Aspecto | LR(0) | SLR(1) | LR(1) | LALR(1) |
|---------|-------|--------|-------|---------|
| Estados en `afn_clausura` | LR(0) | LR(0) | LR(1) | LALR fusionados |
| `afn_lr1` | — | — | — | Sí (pre-fusión) |
| FIRST/FOLLOW en salida | No | Sí | No | No |
| Reduce según | Todos los terminales | FOLLOW(A) | Lookahead ítem | Lookahead ítem |
| Celdas Reduce | `R{k}` | `R{k}` | `R(NT -> …)` | `R(NT -> …)` |
| Aborta si conflictos tabla | Sí | Sí | No* | Sí (fusión) |
| `gramatica_parseable` | No | No | No | No |

\*LR(1) registra conflictos pero puede devolver pasos de simulación.

---

## Integración frontend ↔ backend

### 1. Request único

Enviar siempre `gramatica`, `simbolo_inicial`, `cadena_entrada` y `tipo_parser` al endpoint del backend.

### 2. Tokenización

- Un espacio entre tokens: `id + id * id` (no `id+id` salvo que sea un solo lexema).
- **No** enviar `$`; el servidor lo añade.

### 3. UI recomendada por sección

| Sección | Fuente JSON |
|---------|-------------|
| Resultado cadena | `cadena_valida`, `mensaje` |
| Grafo autómata | `afn_clausura.estados` (todos; paginar en UI si son muchos) |
| Grafo LR(1) previo (LALR) | `afn_lr1.estados` |
| Tabla parseo | `construccion_tablas.columnas` + `filas` |
| FIRST/FOLLOW | `conjuntos_first_follow` (SLR1) |
| Traza | `proceso_paso_a_paso` |
| Conflictos LR1/LALR | `construccion_tablas.conflictos` + `mensaje` |

### 4. Renderizado de `afn_clausura`

- Nodos: `estado` (`I0`, …).
- Aristas: `transiciones[símbolo] → destino`.
- Panel lateral: lista `items`.
- LALR: badge con `lr1_fusionados` (ej. `I1, I6`).

### 5. Épsilon

- En datos JSON: `eps`.
- En UI de ayuda: mostrar `ε` (solo presentación).

### 6. Errores

| Respuesta | Acción UI |
|-----------|-----------|
| `{ "error": "..." }` | Toast; no esperar otros campos |
| `proceso_paso_a_paso.length === 0` y conflicto en `mensaje` | Mostrar tabla/AFN pero no simulación |
| `cadena_valida === false` sin conflicto | Cadena inválida; mostrar traza hasta el error |

### 7. Imports en tests locales

```bash
cd backend/test
python test_lr0.py
python test_slr1.py
python test_lr1.py
python test_lalr1.py
python test_grammar_symbols.py   # colisiones de nombres
```

Los tests usan `import _paths` para añadir `TopDown/` y `BottomUp/` al `sys.path`.

---

## Constantes

| Constante | Valor |
|-----------|--------|
| Épsilon (JSON) | `eps` |
| Fin de entrada | `$` |
| NT aumentado | `{simbolo_inicial}'`, `''`, … (sin colisión) |
| Formato ítem LR(0) | `NT -> símbolos con .` |
| Formato ítem LR(1) | `NT -> … , la1/la2` |

---

## Estructura de archivos

```
backend/
├── grammar_symbols.py   # fresh_prime_name, symbols_in_grammar (nombres sin colisión)
└── BottomUp/
    ├── lr_base.py       # Grammar, LRTable, run_parser (LR1/LALR1)
    ├── lr0_parser.py
    ├── slr1_parser.py   # hereda lógica LR(0)
    ├── lr1_parser.py
    ├── lalr1_parser.py
    └── API.md           # este documento
```
