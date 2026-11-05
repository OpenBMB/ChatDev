/**
 * @name [VARIANT_NAME]
 * @description Find variants of [ORIGINAL_BUG_ID]
 * @kind path-problem
 * @problem.severity error
 * @tags security variant-analysis
 */

import go
import semmle.go.dataflow.TaintTracking
import DataFlow::PathGraph

module VariantConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    // HTTP request values
    exists(DataFlow::CallNode c |
      c.getTarget().hasQualifiedName("net/http", "Request", ["FormValue", "PostFormValue"]) and
      source = c.getResult()
    )
    or
    // URL query params
    exists(DataFlow::CallNode c |
      c.getTarget().hasQualifiedName("net/url", "Values", "Get") and
      source = c.getResult()
    )
    or
    // Gin framework
    exists(DataFlow::CallNode c |
      c.getTarget().hasQualifiedName("github.com/gin-gonic/gin", "Context", ["Query", "Param", "PostForm"]) and
      source = c.getResult()
    )
  }

  predicate isSink(DataFlow::Node sink) {
    // Command injection
    exists(DataFlow::CallNode c |
      c.getTarget().hasQualifiedName("os/exec", "Command") and
      sink = c.getArgument(0)
    )
    or
    // SQL injection
    exists(DataFlow::CallNode c |
      c.getTarget().hasQualifiedName("database/sql", "DB", ["Query", "Exec", "QueryRow"]) and
      sink = c.getArgument(0)
    )
    or
    // Path traversal
    exists(DataFlow::CallNode c |
      c.getTarget().hasQualifiedName("os", ["Open", "OpenFile", "ReadFile"]) and
      sink = c.getArgument(0)
    )
  }

  predicate isBarrier(DataFlow::Node node) {
    exists(DataFlow::CallNode c |
      c.getTarget().getName() in ["Escape", "Quote", "Clean", "ParseInt", "Atoi"] and
      node = c.getResult()
    )
  }
}

module VariantFlow = TaintTracking::Global<VariantConfig>;
import VariantFlow::PathGraph

from VariantFlow::PathNode source, VariantFlow::PathNode sink
where VariantFlow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "Tainted data from $@ flows to dangerous sink.",
  source.getNode(), "user input"
