"""Graph explorer endpoints returning Cytoscape.js topologies and node metrics."""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from backend.app.db.database import get_database
from backend.app.graph.graph_service import GraphService

router = APIRouter(prefix="/api/graph", tags=["graph"])

@router.get("")
def get_graph(
    account_id: Optional[int] = None,
    level: str = Query("domain", pattern="^(domain|sender|thread)$"),
    selected_domain: Optional[str] = None,
    selected_sender_id: Optional[int] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Retrieve multi-resolution Cytoscape.js network graph."""
    db = get_database()
    graph_service = GraphService(db)
    
    return graph_service.get_graph(
        account_id=account_id,
        level=level,
        selected_domain=selected_domain,
        selected_sender_id=selected_sender_id,
        category=category,
        start_date=start_date,
        end_date=end_date
    )
