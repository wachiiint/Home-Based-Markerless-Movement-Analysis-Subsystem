# src/screening.py
def run_rule_based_screening(clinical_metrics):
    """Layer 4: Rule-based decision support system to flag compensations."""
    flags = []
    risk_level = "low"
    
    # Example logic matching documentation thresholds
    if clinical_metrics["compensation"]["trunk_lean_max_angle_deg"] > 15.0:
        flags.append("trunk_compensation")
        risk_level = "moderate"
        
    if clinical_metrics["compensation"]["pelvic_drop_angle_deg"] > 10.0:
        flags.append("possible_trendelenburg_sign")
        risk_level = "moderate"
        
    if len(flags) > 1:
        risk_level = "high"
        
    return {
        "risk_level": risk_level,
        "flags": flags,
        "confidence_score": 0.76 # Baseline prototype confidence
    }