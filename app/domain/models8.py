from typing import Any, Dict, List

def unit_economics(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"model":"unit_economics","score":None,"insights":[],"inputs_required":["price","cogs","cac","ltv","retention_rate","avg_order_value"],"status":"pending"}

def swot(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"model":"swot","score":None,"insights":[],"inputs_required":["strengths","weaknesses","opportunities","threats"],"status":"pending"}

def porter_5_forces(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"model":"porter_5_forces","score":None,"insights":[],"inputs_required":["suppliers_power","buyers_power","new_entrants","substitutes","rivalry"],"status":"pending"}

def pirate_metrics(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"model":"aarrr","score":None,"insights":[],"inputs_required":["acquisition","activation","retention","revenue","referral"],"status":"pending"}

def rice_prioritization(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"model":"rice","score":None,"insights":[],"inputs_required":["initiatives","reach","impact","confidence","effort"],"status":"pending"}

def risk_matrix(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"model":"risk_matrix","score":None,"insights":[],"inputs_required":["risks","probability","impact"],"status":"pending"}

def process_bottlenecks(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"model":"process_bottlenecks","score":None,"insights":[],"inputs_required":["process_map","sla","throughput","queue_lengths"],"status":"pending"}

def financial_health(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"model":"financial_health","score":None,"insights":[],"inputs_required":["cash","runway_months","debt","dscr","gross_margin","ebitda_margin"],"status":"pending"}

def run_all_models(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        unit_economics(payload),
        swot(payload),
        porter_5_forces(payload),
        pirate_metrics(payload),
        rice_prioritization(payload),
        risk_matrix(payload),
        process_bottlenecks(payload),
        financial_health(payload),
    ]
