from app.schemas.common import MonetaryRequest


class ValuationRequest(MonetaryRequest):
    """Base for every valuation request (all accept an optional informational `currency`)."""
