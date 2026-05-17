# Proyecto Bonus Compiladores

Con muuucha (vaquita) fe


### 1. El Input (Lo que recibe el Backend)


```json
{
  "gramatica": "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
  "simbolo_inicial": "E",
  "cadena_entrada": "id * id + id",
  "tipo_parser": "LR1" 
}

```

*(Nota: `tipo_parser` puede ser `"LL1"`, `"LR0"`, `"SLR1"`, `"LALR1"` o `"LR1"` para que el backend sepa a qué función o "silo" enviarlo).*

---

### 2. El Objeto Interno (El "Pre-procesador" en el Backend)

Una vez que el backend recibe el JSON anterior, el texto plano no sirve para hacer algoritmos. El primer paso (que ambos desarrolladores tendrán que hacer o compartir al inicio) es convertir ese texto plano de `gramatica` en un objeto manejable en memoria (ej. una clase o diccionario en Python).

Este sería el estado interno de la memoria una vez procesado:

```python
class Gramatica:
    def __init__(self):
        # 1. Identificar No Terminales (Lado izquierdo de las flechas)
        self.no_terminales = {'E', 'T', 'F'}
        
        # 2. Identificar Terminales (Lo que no es No Terminal)
        # Se añade '$' automáticamente como fin de cadena
        self.terminales = {'+', '*', '(', ')', 'id', '$'} 
        
        self.simbolo_inicial = 'E'
        
        # 3. Mapear Producciones (Lista de listas para mantener el orden)
        # Formato: Diccionario donde la llave es el No Terminal y el valor es una lista de sus derivaciones.
        self.producciones = {
            'E': [['E', '+', 'T'], ['T']],
            'T': [['T', '*', 'F'], ['F']],
            'F': [['(', 'E', ')'], ['id']]
        }
        
        # 4. (Opcional pero útil) Producciones numeradas para los parsers LR (Shift/Reduce)
        self.producciones_numeradas = [
            (0, 'E\'', ['E']),         # Producción aumentada (necesaria para LR)
            (1, 'E', ['E', '+', 'T']),
            (2, 'E', ['T']),
            # ... etc
        ]

```


---

### 3. El Output (El Contrato JSON que devuelve el Backend)


**Ojo con la tabla:** Como las tablas LL(1) y LR(1) son diferentes (LL1 tiene No Terminales en las filas; LR1 tiene Números de Estado), la mejor forma de que el Frontend no colapse es mandar la tabla ya "dibujable".

```json
{
  "cadena_valida": true,
  "mensaje": "La cadena fue aceptada exitosamente.",
  
  "construccion_tablas": {
    "tipo": "LR", 
    "columnas": ["Estado", "id", "+", "*", "(", ")", "$", "E", "T", "F"],
    "filas": [
      {
        "Estado": "0",
        "id": "S5",
        "(": "S4",
        "E": "1",
        "T": "2",
        "F": "3"
      },
      {
        "Estado": "1",
        "+": "S6",
        "$": "ACC"
      }
      // ... resto de estados
    ]
  },
  
  "proceso_paso_a_paso": [
    {
      "paso": 1,
      "pila": "0",
      "entrada": "id * id + id $",
      "accion": "Desplazar (Shift) al estado 5"
    },
    {
      "paso": 2,
      "pila": "0 id 5",
      "entrada": "* id + id $",
      "accion": "Reducir (Reduce) por F -> id"
    },
    {
      "paso": 3,
      "pila": "0 F 3",
      "entrada": "* id + id $",
      "accion": "Reducir (Reduce) por T -> F"
    }
    // ... hasta llegar a Aceptar (ACC) o Error
  ]
}

```
