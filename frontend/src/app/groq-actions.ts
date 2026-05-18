"use server";

import Groq from "groq-sdk";
import type { AnalysisRequest, BackendResult } from "@/lib/backend";

const GROQ_MODEL = "llama-3.3-70b-versatile";

export type GroqTutorMessage = {
    role: "user" | "assistant";
    content: string;
};

export type GroqTutorContext = {
    request: AnalysisRequest;
    result: BackendResult;
    question: string;
    history?: GroqTutorMessage[];
};

function readGroqApiKey(): string {
    const apiKey = process.env.GROQ_API_KEY?.trim();

    if (!apiKey) {
        throw new Error("Falta configurar GROQ_API_KEY en el servidor.");
    }

    return apiKey;
}

function isBackendError(result: BackendResult): result is { error: string; detalles?: unknown } {
    return typeof result === "object" && result !== null && "error" in result;
}

function summarizeResult(result: BackendResult): string {
    if (isBackendError(result)) {
        return [
            "El backend devolvió un error.",
            `Error: ${result.error}`,
            result.detalles ? `Detalles: ${JSON.stringify(result.detalles, null, 2)}` : null,
        ]
            .filter(Boolean)
            .join("\n");
    }

    const conflictSummary = result.construccion_tablas?.conflictos?.length
        ? result.construccion_tablas.conflictos
              .slice(0, 8)
              .map((conflict) => `${conflict.estado} / ${conflict.simbolo}: ${conflict.conflicto}`)
              .join("\n")
        : "Sin conflictos explícitos en la tabla.";

    const transformation = result.sugerencias_transformacion
        ? [
              `Requiere transformación: ${result.sugerencias_transformacion.requiere_transformacion ? "sí" : "no"}`,
              `Motivo: ${result.sugerencias_transformacion.motivo}`,
              result.sugerencias_transformacion.gramatica_sugerida
                  ? `Gramática sugerida:\n${result.sugerencias_transformacion.gramatica_sugerida}`
                  : "Gramática sugerida: no disponible",
          ]
              .filter(Boolean)
              .join("\n")
        : null;

    const followFirst = result.conjuntos_first_follow
        ? JSON.stringify(result.conjuntos_first_follow, null, 2)
        : null;

    const traceSummary = result.proceso_paso_a_paso?.length
        ? result.proceso_paso_a_paso
              .slice(0, 12)
              .map((step) => {
                  const parts = [`Paso ${step.paso}: ${step.accion}`];
                  if (step.pila) parts.push(`Pila=${step.pila}`);
                  if (step.entrada) parts.push(`Entrada=${step.entrada}`);
                  return parts.join(" | ");
              })
              .join("\n")
        : "Sin traza paso a paso disponible.";

    return [
        `Cadena válida: ${result.cadena_valida ? "sí" : "no"}`,
        `Mensaje del backend: ${result.mensaje}`,
        result.gramatica_parseable === undefined ? null : `Gramática parseable: ${result.gramatica_parseable ? "sí" : "no"}`,
        conflictSummary ? `Conflictos:\n${conflictSummary}` : null,
        transformation ? `Transformación:\n${transformation}` : null,
        followFirst ? `FIRST/FOLLOW:\n${followFirst}` : null,
        `Traza resumida:\n${traceSummary}`,
    ]
        .filter(Boolean)
        .join("\n\n");
}

function buildSystemPrompt(context: GroqTutorContext): string {
    const result = context.result;
    const parserType = context.request.tipo_parser;
    const originalGrammar = context.request.gramatica.trim() || "(vacía)";
    const inputChain = context.request.cadena_entrada.trim() || "(vacía)";
    const baseSummary = summarizeResult(result);

    return [
        "Eres un tutor académico de teoría de compiladores.",
        "Responde siempre en español, con precisión y tono didáctico.",
        "Devuelve la explicación en markdown simple para que la interfaz pueda mostrar títulos, listas, énfasis y bloques de código.",
        "Usa bloques de código cuando muestres gramáticas, trazas o ejemplos largos.",
        "No inventes datos que no estén en el contexto.",
        "Si falta información, dilo de forma breve y explícita.",
        "Si el usuario pide corregir la gramática, sugiere cambios concretos y explica por qué.",
        "Si hay conflictos, explica el tipo de conflicto, qué lo causa y cómo suele resolverse.",
        "No reveles razonamiento interno detallado; entrega solo la explicación útil.",
        "",
        `Tipo de parser: ${parserType}`,
        `Cadena de entrada: ${inputChain}`,
        `Gramática original:\n${originalGrammar}`,
        `Resumen del análisis:\n${baseSummary}`,
    ].join("\n");
}

export async function askGroqTutor(context: GroqTutorContext): Promise<string> {
    const client = new Groq({ apiKey: readGroqApiKey() });
    const systemPrompt = buildSystemPrompt(context);

    const messages = [
        { role: "system" as const, content: systemPrompt },
        ...(context.history ?? []).slice(-8).map((message) => ({
            role: message.role,
            content: message.content,
        })),
        { role: "user" as const, content: context.question.trim() },
    ];

    const response = await client.chat.completions.create({
        model: GROQ_MODEL,
        messages,
        temperature: 0.2,
    });

    const content = response.choices[0]?.message?.content?.trim();

    if (!content) {
        throw new Error("Groq no devolvió una respuesta utilizable.");
    }

    return content;
}