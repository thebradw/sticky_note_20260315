from .base import WorkflowLayoutStrategy
from .single_column import SingleColumnStrategy
from .newspaper import NewspaperColumnsStrategy
from .horizontal_swim_lanes import HorizontalSwimLaneStrategy
from .vertical_swim_lanes import VerticalSwimLaneStrategy

_single_column = SingleColumnStrategy()

LAYOUT_STRATEGIES = {
    'single-column': _single_column,
    'left-right': _single_column,  # legacy alias
    'newspaper': NewspaperColumnsStrategy(),
    'horizontal-swim-lanes': HorizontalSwimLaneStrategy(),
    'vertical-swim-lanes': VerticalSwimLaneStrategy(),
}

def get_layout_strategy(flow_direction):
    """Return the registered strategy, defaulting to single-column."""
    return LAYOUT_STRATEGIES.get(flow_direction, _single_column)

__all__ = [
    'WorkflowLayoutStrategy',
    'LAYOUT_STRATEGIES',
    'get_layout_strategy',
]
