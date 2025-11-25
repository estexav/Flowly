import os
import json
import requests
from typing import List, Dict, Any, Optional
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # Si python-dotenv no está disponible, continuamos sin romper.
    pass


# API endpoint (REST) para modelos generativos
DEFAULT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _gemini_call(prompt: str, api_key: Optional[str] = None, temperature: float = 0.7, max_output_tokens: int = 1024) -> str:
    """Realiza una llamada REST al modelo generativo.

    Retorna texto generado o cadena vacía si falla o no hay API key.
    """
    key = (api_key or os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        return ""
    url = f"{DEFAULT_URL}?key={key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        },
    }
    try:
        r = requests.post(url, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=20)
        r.raise_for_status()
        j = r.json()
        return j["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return ""


def summarize_transactions(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcula ingresos, gastos, disponible y gastos por categoría."""
    incomes = 0.0
    expenses = 0.0
    by_category: Dict[str, float] = {}
    for t in transactions or []:
        amount = float(t.get("amount", 0.0))
        ttype = t.get("type", "")
        cat = t.get("category", "General")
        if ttype.lower().startswith("ingreso"):
            incomes += amount
        elif ttype.lower().startswith("gasto"):
            expenses += amount
            by_category[cat] = by_category.get(cat, 0.0) + amount
    disposable = incomes - expenses
    return {
        "incomes": incomes,
        "expenses": expenses,
        "disposable": disposable,
        "by_category": by_category,
    }


def purchase_advice(summary: Dict[str, Any]) -> str:
    """Genera consejos de compra basados en el disponible (heurístico)."""
    disposable = float(summary.get("disposable", 0.0))
    small = max(0.0, disposable * 0.05)
    medium = max(0.0, disposable * 0.15)
    large = max(0.0, disposable * 0.30)
    by_cat = summary.get("by_category", {})
    top_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:3]
    cats_text = ", ".join([f"{c} (${v:.2f})" for c, v in top_cats]) or "sin datos"
    return (
        "Sugerencias de compra prudentes basadas en tu disponible:\n"
        f"- Pequeñas: hasta ${small:.2f}\n"
        f"- Medianas: hasta ${medium:.2f}\n"
        f"- Grandes: hasta ${large:.2f} (evita si compromete tu ahorro)\n"
        f"Categorías más altas: {cats_text}. Considera límites y comparativas por unidad.\n"
    )


def predict_spending(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Predice gastos próximos por categoría (heurístico + IA opcional).

    Si hay clave de API, genera texto explicativo; siempre retorna datos numéricos.
    """
    summary = summarize_transactions(transactions)
    expenses = summary["expenses"]
    by_cat = summary["by_category"]
    total = max(expenses, 1.0)
    # Distribución actual y presupuesto sugerido (reduce 10% en top 2)
    dist = {cat: val / total for cat, val in by_cat.items()}
    sorted_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
    reduce_set = {c for c, _ in sorted_cats[:2]}
    suggested_budget = {cat: val * (0.9 if cat in reduce_set else 1.0) for cat, val in by_cat.items()}

    # Texto IA opcional
    cat_lines = ", ".join([f"{c}: ${v:.2f}" for c, v in by_cat.items()]) or "sin datos"
    prompt = (
        "Actúa como asesor financiero. Habla en español y directo.\n"
        "Con esta distribución de gastos por categoría y el total mensual actual, sugiere un presupuesto para el próximo mes,\n"
        "priorizando ahorro y reducción en categorías altas. Incluye cifras estimadas y recomendaciones accionables.\n"
        f"Gasto total: ${expenses:.2f}. Por categoría: {cat_lines}.\n"
    )
    ai_text = _gemini_call(prompt)
    if not ai_text:
        ai_text = (
            "Predicción heurística: reduce 10% en las 2 categorías con mayor gasto, \n"
            "mantén las demás, y evalúa ajustar suscripciones. Usa límites semanales y seguimiento." 
        )

    return {
        "summary": summary,
        "distribution": dist,
        "suggested_budget": suggested_budget,
        "advice": ai_text,
    }


def chat_finance(message: str, transactions: List[Dict[str, Any]]) -> str:
    """Chat financiero: responde preguntas libres considerando ingresos/gastos y disponible."""
    summary = summarize_transactions(transactions)
    cat_lines = ", ".join([f"{c}: ${v:.2f}" for c, v in summary["by_category"].items()]) or "sin datos"
    prompt = (
        "Eres un asesor financiero responsable. Responde en español y con pasos concretos.\n"
        "Contexto: "
        f"Ingresos ${summary['incomes']:.2f}, Gastos ${summary['expenses']:.2f}, Disponible ${summary['disposable']:.2f}. "
        f"Por categoría: {cat_lines}.\n"
        "Pregunta del usuario: '" + (message or "") + "'.\n"
        "Incluye cifras estimadas cuando aplique, sugiere límites y alternativas más baratas. Evita promover endeudamiento riesgoso.\n"
    )
    ai_text = _gemini_call(prompt)
    if ai_text:
        return ai_text

    # Fallback heurístico
    disposable = summary["disposable"]
    small = max(0.0, disposable * 0.05)
    medium = max(0.0, disposable * 0.15)
    large = max(0.0, disposable * 0.30)
    return (
        "Consejo general basado en tus datos:\n"
        f"- Disponible mensual: ${disposable:.2f}.\n"
        f"- Rangos prudentes: pequeñas ${small:.2f}, medianas ${medium:.2f}, grandes ${large:.2f}.\n"
        "- Define límites por categoría, revisa suscripciones y compara precios por unidad.\n"
        "- Evita deuda salvo tasa 0% y con plan claro de pago.\n"
    )


def quick_prompt_response(kind: str, transactions: List[Dict[str, Any]]) -> str:
    """Respuestas específicas para chips predefinidas.

    - "resumen": resumen mensual con top categorías y sugerencias.
    - "recortes": plan de recortes con estimación de ahorro por categoría.
    - "compra_grande": guía para evaluar compra grande este mes.
    - "presupuesto_semanal": límites semanales por categoría.
    Si hay API key, intenta generar texto enriquecido; si falla, usa heurística diferenciada.
    """
    kind = (kind or "").strip().lower()
    summary = summarize_transactions(transactions)
    incomes = float(summary.get("incomes", 0.0))
    expenses = float(summary.get("expenses", 0.0))
    disposable = float(summary.get("disposable", 0.0))
    by_cat = summary.get("by_category", {})
    cat_lines = ", ".join([f"{c}: ${v:.2f}" for c, v in by_cat.items()]) or "sin datos"

    # Intento IA (texto más rico) según el tipo
    prompt_map = {
        "resumen": (
            "Actúa como asesor financiero y entrega un resumen mensual conciso en español. "
            f"Ingresos ${incomes:.2f}, gastos ${expenses:.2f}, disponible ${disposable:.2f}. "
            f"Por categoría: {cat_lines}. "
            "Incluye 3 observaciones y 3 recomendaciones claras (con cifras cuando aplique)."
        ),
        "recortes": (
            "Explica de forma muy simple dónde recortar sin afectar mucho. "
            f"Top categorías: {cat_lines}. "
            "Da porcentajes y ahorro estimado en una lista corta."
        ),
        "comprar_algo": (
            "Responde de forma simple cuánto es seguro gastar en una compra. "
            f"Ingresos ${incomes:.2f}, gastos ${expenses:.2f}, disponible ${disposable:.2f}. "
            "Incluye monto seguro y umbral a evitar."
        ),
        "presupuesto_semanal": (
            "Sugiere un presupuesto semanal por categoría en español, basado en el gasto actual y un ajuste conservador. "
            f"Por categoría: {cat_lines}. Incluye límites numéricos por semana y tips de control."
        ),
    }
    ai_text = _gemini_call(prompt_map.get(kind, "")) if prompt_map.get(kind) else ""
    if ai_text:
        return ai_text

    # Heurísticas diferenciadas (sin IA)
    sorted_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
    top3 = sorted_cats[:3]

    if kind == "resumen":
        top_str = ", ".join([f"{c} (${v:.2f})" for c, v in top3]) or "sin datos"
        return (
            "Resumen mensual basado en tus datos:\n"
            f"- Ingresos: ${incomes:.2f}\n"
            f"- Gastos: ${expenses:.2f}\n"
            f"- Disponible: ${disposable:.2f}\n"
            f"- Categorías con mayor gasto: {top_str}\n"
            "Recomendaciones: define límites por categoría, revisa suscripciones y compara precios por unidad."
        )

    if kind == "recortes":
        # Reducciones simples: 10% y 5% en top 2 (mensaje corto)
        perc = [0.10, 0.05]
        savings_lines = []
        total_save = 0.0
        for i, (c, v) in enumerate(top3[:2]):
            p = perc[i]
            s = v * p
            savings_lines.append(f"- {c}: baja {int(p*100)}% → ahorras ${s:.2f}")
            total_save += s
        lines = "\n".join(savings_lines) or "- Sin datos"
        return (
            "Recortes fáciles (sin complicaciones):\n"
            f"{lines}\n"
            f"Ahorro mensual estimado: ${total_save:.2f}. Cancela suscripciones que no uses y compra por unidad."
        )

    if kind == "comprar_algo":
        # Monto seguro simple: 25% del disponible, con mínimo 0
        safe = max(0.0, disposable * 0.25)
        avoid_threshold = max(0.0, disposable * 0.60)
        return (
            "Comprar algo (respuesta simple):\n"
            f"- Disponible mensual: ${disposable:.2f}\n"
            f"- Monto seguro para gastar: ${safe:.2f}\n"
            f"- Evita compras > ${avoid_threshold:.2f}; mejor planifica y ahorra."
        )

    if kind == "presupuesto_semanal":
        pred = predict_spending(transactions)
        suggested = pred.get("suggested_budget", {})
        weekly = {c: v / 4.0 for c, v in suggested.items()}
        lines = "\n".join([f"- {c}: ${w:.2f}/semana" for c, w in weekly.items()]) or "- Sin datos"
        return (
            "Presupuesto semanal sugerido por categoría:\n"
            f"{lines}\n"
            "Usa límites por semana y alerta si superas 80% del tope."
        )

    # Fallback si no coincide ningún tipo
    return chat_finance(kind, transactions)
