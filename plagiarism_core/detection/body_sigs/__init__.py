"""Body signature extraction functions."""

from .comprehensions import (
    _extract_comprehension_parts as _extract_comprehension_parts,
)
from .comprehensions import (
    _extract_comprehension_pattern as _extract_comprehension_pattern,
)
from .comprehensions import (
    _extract_loop_append_pattern as _extract_loop_append_pattern,
)
from .comprehensions import (
    _extract_map_lambda_parts as _extract_map_lambda_parts,
)
from .conditionals import (
    _extract_conditional_assign_signature as _extract_conditional_assign_signature,
)
from .conditionals import (
    _extract_lbyl_signature as _extract_lbyl_signature,
)
from .conditionals import (
    _extract_nested_if_signature as _extract_nested_if_signature,
)
from .conditionals import (
    _extract_return_value as _extract_return_value,
)
from .conditionals import (
    _extract_ternary_signature as _extract_ternary_signature,
)
from .conditionals import (
    _extract_try_signature as _extract_try_signature,
)
from .dispatcher import (
    _extract_body_signature as _extract_body_signature,
)
from .returns import (
    _extract_dict_pattern as _extract_dict_pattern,
)
from .returns import (
    _extract_return_chain_signature as _extract_return_chain_signature,
)
from .returns import (
    _extract_tuple_return_signature as _extract_tuple_return_signature,
)

__all__ = [
    "_extract_body_signature",
    "_extract_comprehension_pattern",
    "_extract_comprehension_parts",
    "_extract_conditional_assign_signature",
    "_extract_dict_pattern",
    "_extract_lbyl_signature",
    "_extract_loop_append_pattern",
    "_extract_map_lambda_parts",
    "_extract_nested_if_signature",
    "_extract_return_chain_signature",
    "_extract_return_value",
    "_extract_ternary_signature",
    "_extract_try_signature",
    "_extract_tuple_return_signature",
]
