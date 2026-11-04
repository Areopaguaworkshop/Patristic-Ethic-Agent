"""Validate the frozen CLI result before mapping it to host authority."""


def validate_result(result: object) -> dict:
    if not isinstance(result, dict) or result.get("action") not in {
        "proceed", "guide", "refuse", "clarify", "review", "withhold",
    }:
        raise ValueError("invalid assessment action")
    if result["action"] in {"proceed", "guide"} and result.get("failure") is not None:
        raise ValueError("failed assessment cannot forward")
    if result["action"] == "proceed":
        decision = result.get("decision")
        if not isinstance(decision, dict) or decision.get("disposition") != "allow":
            raise ValueError("proceed requires an allow decision")
    return result
