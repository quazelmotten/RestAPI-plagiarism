; Tree-sitter queries for Python language
; These queries enable declarative pattern extraction for common operations

; Extract function definitions with name and parameters
; Captures: @function - the entire function node
;            @name - the function name identifier
;            @params - all parameter identifiers
(function_definition
  name: (identifier) @name
  parameters: (parameters
    (identifier) @param
  ) @function
)

; Extract function definitions that include 'self' parameter (needs special handling)
(function_definition
  name: (identifier) @name
  parameters: (parameters
    (identifier) @param
    (#match? @param "^(self|cls)$")
  ) @function.with_self
)

; Extract class definitions with name and body
(class_definition
  name: (identifier) @name
  body: (block) @body
)

; Extract methods inside classes
(class_definition
  body: (block
    (function_definition
      name: (identifier) @method_name
      parameters: (parameters
        (identifier) @param
      ) @method
    )
  )
)

; Extract expression statements that contain lambda assignments
; (for detecting lambdas assigned to variables)
(expression_statement
  (assignment
    left: (identifier) @lambda_name
    right: (lambda) @lambda
  )
)

; Extract all identifiers
(identifier) @identifier

; Extract operators (binary, unary, comparison)
(binary_operator) @operator
(unary_operator) @operator
(comparison_operator) @operator

; Extract literals (string, integer, float, boolean, nil)
(string) @literal
(integer) @literal
(float) @literal
(true) @literal
(false) @literal
(nil) @literal
