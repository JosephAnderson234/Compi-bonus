# Bottom-Up — Contrato de API

Parsers **LR** para análisis ascendente. Tres interfaces principales:

| Módulo | Función | Tipo de tabla |
|--------|---------|----------------|
| `lr0_parser.py` | `run_analysis(input_data)` | LR(0) |
| `slr1_parser.py` | `run_analysis(input_data)` | SLR(1) |
| `lr1_parser.py` | `run_analysis(input_data)` / `parse_request(request)` | LR(1) |

`LR1.py` define la misma clase `ParserLR1` y método `run(tokens)`; `lr1p.py` es el adaptador con entrada tipo concurso (`gramatica`, `simbolo_inicial`, `cadena_entrada`).

Infraestructura compartida LR(1): `LRBase.py` (`Grammar`, `LRTable`, `run_parser`).

```python
from lr0_parser import run_analysis as analyze_lr0
from slr1_parser import run_analysis as analyze_slr1
from lr1p import parse_request as analyze_lr1
```

---

## Entrada común (LR0 y SLR1)

`run_analysis(input_data)` — dict con **tres claves obligatorias**:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `gramatica` | `string` | Una producción por línea: `NT -> alt1 \| alt2`. |
| `simbolo_inicial` | `string` | No terminal inicial de la gramática **original** (antes de aumentar). |
| `cadena_entrada` | `string` | Tokens separados por espacio; el parser añade `$` al final. |

### Formato de gramática (LR0 / SLR1)

- Igual que Top-Down en estructura (`->`, `|`, espacios).
- **Épsilon:** solo el token literal **`eps`** (o alternativa vacía tras `|`, que se interpreta como `eps`).
- Producción `A -> eps` se almacena internamente como cuerpo vacío `()`.

Ejemplo:

```text
E  -> T E'
E' -> + T E' | eps
T  -> F T'
T' -> * F T' | eps
F  -> ( E ) | id
```

### Gramática aumentada (automática)

El backend crea `S' -> S` (sufijo `'` en el NT aumentado, p. ej. `E'` si `S = E`). No hace falta escribirla en `gramatica`.

---

## Entrada LR(1) (`parse_request`)

Mismas claves que LR0/SLR1, más opcional:

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `tipo_parser` | `string` | `"LR1"` | Debe ser `"LR1"`; otro valor devuelve `{ "error": "..." }`. |

Parseo vía `Grammar.from_text()` en `lr_base.py`:

- Tokens por espacios.
- Épsilon: token **`eps`**, símbolo **`ε`** en texto, o alternativa vacía tras `|` (como LR0).
- Producción `A -> eps` → cuerpo vacío interno; en JSON/salida se muestra **`eps`**.
- Se inserta automáticamente la producción aumentada `S' -> simbolo_inicial`.

```json
{
  "gramatica": "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
  "simbolo_inicial": "E",
  "cadena_entrada": "id * id + id",
  "tipo_parser": "LR1"
}
```

---

## Salida común (LR0 y SLR1)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `cadena_valida` | `boolean` | Cadena aceptada por shift-reduce. |
| `mensaje` | `string` | Éxito, rechazo o gramática con conflictos. |
| `construccion_tablas` | `object` | Tabla ACTION/GOTO unificada. |
| `proceso_paso_a_paso` | `array` | Simulación; `[]` si hay conflictos y se aborta. |

**Nota:** LR0/SLR1 **no** exponen `gramatica_parseable`. La gramática “válida para el método” equivale a **no tener conflictos** al construir la tabla; el frontend puede derivar:

`gramatica_compatible = (proceso_paso_a_paso.length > 0 || cadena_valida) && !mensaje.includes('conflictos')`

o inspeccionar si `mensaje` indica conflictos LR(0)/SLR(1).

### `proceso_paso_a_paso` (LR0 / SLR1)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `paso` | `number` | Número de paso. |
| `pila` | `string` | Pila LR: estados y símbolos intercalados (`0 id 5 * 7`). |
| `entrada` | `string` | Entrada restante incluyendo `$`. |
| `accion` | `string` | Ej.: `Desplazar (Shift) al estado 5`, `Reducir (Reduce) por E -> T E'`, `ACEPTAR`, `ERROR: ...`. |

En reducciones con épsilon, la regla se muestra como `A -> eps`.

### `construccion_tablas` (LR0 / SLR1)

```json
{
  "tipo": "LR0",
  "columnas": ["Estado", "(", ")", "*", "+", "id", "$", "E", "E'", "F", "T", "T'"],
  "filas": [
    {
      "Estado": "0",
      "id": "S5",
      "E": "3",
      "$": "ACC"
    }
  ]
}
```

| Celda | Significado |
|-------|-------------|
| `S{n}` | Shift al estado `n`. |
| `R{k}` | Reduce usando la producción índice `k` (orden interno de `prod_list`). |
| `ACC` | Aceptar. |
| Número solo (columna NT) | GOTO al estado indicado. |
| Clave ausente | Sin acción. |

`tipo` es `"LR0"` o `"SLR1"` según el módulo.

### SLR(1) — campo extra

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `conjuntos_first_follow` | `object` | Igual que LL(1): por NT, `FIRST` y `FOLLOW` (épsilon = `"eps"`). |

---

## Salida LR(1) (`parse_request` / `ParserLR1.run`)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `cadena_valida` | `boolean` | |
| `mensaje` | `string` | |
| `afn_clausura` | `object` | Autómata de ítems LR(1) (grafos de estados). |
| `construccion_tablas` | `object` | Tabla LR(1) + posibles conflictos. |
| `proceso_paso_a_paso` | `array` | Misma forma que en `LRBase.run_parser`. |

### `afn_clausura`

```json
{
  "tipo": "LR1",
  "estados": [
    {
      "estado": "I0",
      "items": ["E' -> . E , $", "E -> . E + T , +/$", "..."],
      "transiciones": { "E": "I1", "(": "I2" }
    }
  ]
}
```

- `items`: cadenas con punto y lookaheads (`/` entre lookahead).
- `transiciones`: símbolo → id de estado destino (`I{n}`).

### `construccion_tablas` (LR1)

```json
{
  "tipo": "LR1",
  "columnas": ["Estado", "$", "id", "...", "E", "T", "F"],
  "filas": [{ "Estado": "0", "id": "S5", "E": "1" }],
  "conflictos": [
    { "estado": 3, "simbolo": "id", "conflicto": "S5 vs R(E -> T)" }
  ]
}
```

Acciones en celdas (vía `Action.to_str()`):

| Texto | Significado |
|-------|-------------|
| `S{n}` | Shift |
| `R(NT -> cuerpo)` | Reduce por producción |
| `ACC` | Aceptar |
| (vacío) | Sin acción |

### `proceso_paso_a_paso` (LR1)

Igual estructura que LR0 (`paso`, `pila`, `entrada`, `accion`). Textos: `Desplazar (Shift) al estado n`, `Reducir (Reduce) por NT -> cuerpo`, `Aceptar (ACC)`.

---

## Comparativa rápida

| Aspecto | LR(0) | SLR(1) | LR(1) |
|---------|-------|--------|-------|
| Función | `lr0_parser.run_analysis` | `slr1_parser.run_analysis` | `lr1p.parse_request` |
| FIRST/FOLLOW en salida | No | Sí | No (lookaheads en ítems) |
| AFN de clausura | No | No | Sí (`afn_clausura`) |
| Criterio Reduce | Todos los terminales del estado | Solo `FOLLOW(A)` | Por lookahead en ítem |
| Épsilon en gramática | `eps` | `eps` (hereda LR0) | `eps` (token explícito) |
| Conflictos | Aborta simulación | Aborta + mensaje detallado | Lista en `conflictos` |

---

## Integración frontend ↔ backend

1. **Tokenización en cliente o servidor:** `cadena_entrada` siempre con espacios (`id + id`, no `id+id` salvo que `+` sea un solo token pegado).
2. **No enviar `$`** en la cadena; los parsers lo agregan.
3. **Selector de algoritmo:** mapear UI a `run_analysis` (LR0/SLR1) o `parse_request` (LR1).
4. **Tablas:** renderizar `construccion_tablas.columnas` + `filas`; celdas opcionales = vacío.
5. **LR(1):** vista de grafo desde `afn_clausura.estados`; tabla desde `construccion_tablas`; revisar `conflictos` si existe.
6. **Épsilon:** mostrar `eps` en datos JSON; en ayudas al usuario se puede mostrar ε (como en tests).
7. **Conflictos LR(0)/SLR(1):** `cadena_valida === false`, `proceso_paso_a_paso === []`, `mensaje` describe conflictos — no hay tabla válida para simular.

### Respuesta LR(0) sin conflictos (fragmento)

```json
{
  "cadena_valida": true,
  "mensaje": "Análisis sintáctico completado exitosamente sin conflictos LR(0).",
  "construccion_tablas": {
    "tipo": "LR0",
    "columnas": ["Estado", "id", "$", "E", "T"],
    "filas": []
  },
  "proceso_paso_a_paso": [
    {
      "paso": 1,
      "pila": "0",
      "entrada": "id $",
      "accion": "Desplazar (Shift) al estado 5"
    }
  ]
}
```

### Error LR(1) tipo parser

```json
{
  "error": "tipo_parser 'LR0' no soportado en lr1_parser (solo LR1)"
}
```

### Tests locales

```bash
cd backend/test
python test_lr0.py
python test_slr1.py
python test_lr1.py
```

---

## Constantes (referencia)

| Constante | Valor | Ámbito |
|-----------|--------|--------|
| Épsilon | `eps` | LR0, SLR1, gramática LR(1) vía texto |
| Fin de entrada | `$` | Todos |
| NT aumentado | `{simbolo_inicial}'` | LR0, SLR1, LR(1) |
